import queue
import threading
import time
import re
from collections import deque

import numpy as np
import sounddevice as sd
import whisper
import serial

from elevenlabs.client import ElevenLabs
from elevenlabs.play import play

from google import genai
from google.genai import types


# ============================================================
# CONFIG
# ============================================================
SAMPLE_RATE = 16000

# Use tiny.en first for speed.
# If your machine can keep up, try "base.en" for better accuracy.
MODEL_NAME = "tiny.en"

WAKE_WORD = "fish"

# Wake detection chunking
WAKE_WINDOW_SEC = 1.2
WAKE_STEP_SEC = 0.35
PRE_ROLL_SEC = 0.6

# Command capture
COMMAND_MAX_SEC = 6.0
SILENCE_HOLD_SEC = 0.9
VOICE_RMS_THRESHOLD = 0.015   # tune this for your mic / background noise
COOLDOWN_SEC = 1.0

# Serial
PORT = "/dev/ttyACM0"
BAUD = 9600

# ElevenLabs
VOICE_ID = "Bj9UqZbhQsanLzgalpEG"
ELEVEN_MODEL_ID = "eleven_multilingual_v2"
ELEVEN_OUTPUT_FORMAT = "mp3_44100_128"


# ============================================================
# HELPERS
# ============================================================
def get_api_key(file_path: str):
    try:
        with open(file_path, "r") as f:
            return f.readline().strip()
    except FileNotFoundError:
        print(f"Error: file not found -> {file_path}")
        return None


def normalize_text(text: str) -> str:
    return re.sub(r"[^a-z0-9\s]", " ", text.lower()).strip()


def heard_wake_word(text: str, wake_word: str = WAKE_WORD) -> bool:
    words = normalize_text(text).split()
    return wake_word in words


def strip_leading_wake_word(text: str, wake_word: str = WAKE_WORD) -> str:
    pattern = rf"^\s*{re.escape(wake_word)}\b[\s,.:;!?-]*"
    return re.sub(pattern, "", text, flags=re.IGNORECASE).strip()


def rms(audio: np.ndarray) -> float:
    if len(audio) == 0:
        return 0.0
    audio = audio.astype(np.float32, copy=False)
    return float(np.sqrt(np.mean(audio * audio)))


def clear_queue(q: queue.Queue):
    try:
        while True:
            q.get_nowait()
    except queue.Empty:
        pass


# ============================================================
# SERIAL CONTROLLER
# ============================================================
class FishSerial:
    """
    b'0' -> idle
    b'1' -> thinking / wake listening
    b'2' -> listening for command
    b'3' -> speaking
    """
    def __init__(self, port=PORT, baud=BAUD):
        self.ser = None
        try:
            self.ser = serial.Serial(port, baud, timeout=1)
            print(f"Serial connected on {port}")
        except Exception as e:
            print(f"Serial disabled: {e}")

    def write(self, data: bytes):
        if self.ser is None:
            return
        try:
            self.ser.write(data)
        except Exception as e:
            print(f"Serial write failed: {e}")

    def close(self):
        if self.ser is None:
            return
        try:
            self.ser.close()
        except Exception:
            pass


# ============================================================
# ASSISTANT
# ============================================================
class FishAssistant:
    def __init__(self):
        # Audio / STT queues
        self.audio_q = queue.Queue()
        self.transcribe_job_q = queue.Queue(maxsize=1)
        self.transcribe_result_q = queue.Queue()
        self.stop_event = threading.Event()

        # Clients
        self.gemini_client = None
        self.eleven_client = None
        self.fish_serial = FishSerial()

        # Whisper worker thread
        self.worker_thread = None

        # Stream
        self.stream = None

        # State
        self.state = "WAIT_WAKE"  # WAIT_WAKE, RECORD_COMMAND, WAIT_COMMAND_TRANSCRIPT
        self.cooldown_until = 0.0
        self.last_wake_submit = 0.0

        self.command_chunks = []
        self.command_samples = 0
        self.silence_samples = 0
        self.speech_started = False

        # Buffer lengths
        self.wake_samples = int(WAKE_WINDOW_SEC * SAMPLE_RATE)
        self.preroll_samples = int(PRE_ROLL_SEC * SAMPLE_RATE)
        self.max_command_samples = int(COMMAND_MAX_SEC * SAMPLE_RATE)
        self.silence_hold_samples = int(SILENCE_HOLD_SEC * SAMPLE_RATE)

        # Rolling ring buffer for wake chunks + pre-roll
        self.ring = deque(maxlen=self.wake_samples + self.preroll_samples)

    # --------------------------------------------------------
    # Setup
    # --------------------------------------------------------
    def setup_clients(self):
        gemini_key = get_api_key("../media/gemini_api_key.txt")
        eleven_key = get_api_key("../media/elevenLabs_key.txt")

        if gemini_key is None:
            raise RuntimeError("Missing Gemini API key.")
        if eleven_key is None:
            raise RuntimeError("Missing ElevenLabs API key.")

        self.gemini_client = genai.Client(api_key=gemini_key)
        self.eleven_client = ElevenLabs(api_key=eleven_key)

    def audio_callback(self, indata, frames, time_info, status):
        if status:
            print(status)
        self.audio_q.put(indata[:, 0].copy())

    def transcribe_worker(self):
        print(f"Loading Whisper model: {MODEL_NAME}")
        model = whisper.load_model(MODEL_NAME)
        print("Whisper loaded.")

        while not self.stop_event.is_set():
            try:
                job = self.transcribe_job_q.get(timeout=0.1)
            except queue.Empty:
                continue

            if job is None:
                break

            job_type, audio = job

            try:
                result = model.transcribe(
                    audio,
                    language="en",
                    fp16=False,
                    verbose=False,
                    temperature=0,
                    condition_on_previous_text=False,
                )
                text = result.get("text", "").strip()
            except Exception as e:
                print(f"[transcribe error] {e}")
                text = ""

            self.transcribe_result_q.put((job_type, text))

    def start_worker(self):
        self.worker_thread = threading.Thread(
            target=self.transcribe_worker,
            daemon=True
        )
        self.worker_thread.start()

    def start_stream(self):
        if self.stream is None:
            self.stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="float32",
                blocksize=int(0.05 * SAMPLE_RATE),  # 50 ms
                callback=self.audio_callback,
            )
        self.stream.start()

    def stop_stream(self):
        if self.stream is not None:
            self.stream.stop()

    # --------------------------------------------------------
    # State helpers
    # --------------------------------------------------------
    def set_idle_listening(self):
        self.state = "WAIT_WAKE"
        self.command_chunks = []
        self.command_samples = 0
        self.silence_samples = 0
        self.speech_started = False
        self.fish_serial.write(b'1')
        print("Listening continuously... say 'fish'")

    def begin_command_capture(self):
        pre = np.array(list(self.ring)[-self.preroll_samples:], dtype=np.float32)
        self.command_chunks = [pre]
        self.command_samples = len(pre)
        self.silence_samples = 0
        self.speech_started = False
        self.state = "RECORD_COMMAND"
        self.fish_serial.write(b'2')
        print("[recording command...]")

    def finalize_command_capture(self):
        full_audio = np.concatenate(self.command_chunks).astype(np.float32)
        if self.transcribe_job_q.empty():
            self.transcribe_job_q.put(("command", full_audio))
            self.state = "WAIT_COMMAND_TRANSCRIPT"
            self.fish_serial.write(b'1')
            print("[transcribing full command...]")

    # --------------------------------------------------------
    # AI pipeline
    # --------------------------------------------------------
    def ask_llm(self, text: str) -> str:
        response = self.gemini_client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=text,
            config=types.GenerateContentConfig(
                system_instruction="""
                You are a witty and helpful fish on the wall.
                Make really smart remarks.
                Keep responses to roughly 20 words.
                Keep the grammar simple.
                """
            )
        )
        return response.text.strip()

    def speak(self, text: str):
        audio_stream = self.eleven_client.text_to_speech.convert(
            text=text,
            voice_id=VOICE_ID,
            model_id=ELEVEN_MODEL_ID,
            output_format=ELEVEN_OUTPUT_FORMAT,
        )
        self.fish_serial.write(b'3')
        play(audio_stream)
        self.fish_serial.write(b'0')

    def handle_command(self, text: str):
        print(f"\n[USER] {text}\n")

        self.fish_serial.write(b'1')
        reply = self.ask_llm(text)

        print(f"[FISH] {reply}\n")
        self.speak(reply)

    # --------------------------------------------------------
    # Main loop
    # --------------------------------------------------------
    def run(self):
        self.setup_clients()
        self.start_worker()
        self.start_stream()
        self.set_idle_listening()

        try:
            while True:
                # --------------------------------------------
                # Drain incoming audio
                # --------------------------------------------
                drained_any = False
                while True:
                    try:
                        frame = self.audio_q.get(timeout=0.02 if not drained_any else 0.0)
                        drained_any = True
                    except queue.Empty:
                        break

                    # keep rolling history always
                    self.ring.extend(frame)

                    if self.state == "RECORD_COMMAND":
                        self.command_chunks.append(frame.copy())
                        self.command_samples += len(frame)

                        frame_rms = rms(frame)
                        if frame_rms > VOICE_RMS_THRESHOLD:
                            self.speech_started = True
                            self.silence_samples = 0
                        elif self.speech_started:
                            self.silence_samples += len(frame)

                        hit_max_len = self.command_samples >= self.max_command_samples
                        hit_silence = (
                            self.speech_started and
                            self.silence_samples >= self.silence_hold_samples
                        )

                        if hit_max_len or hit_silence:
                            self.finalize_command_capture()

                # --------------------------------------------
                # Submit wake-listening chunk jobs
                # --------------------------------------------
                now = time.time()
                if (
                    self.state == "WAIT_WAKE"
                    and now >= self.cooldown_until
                    and len(self.ring) >= self.wake_samples
                    and (now - self.last_wake_submit) >= WAKE_STEP_SEC
                    and self.transcribe_job_q.empty()
                ):
                    recent = np.array(list(self.ring)[-self.wake_samples:], dtype=np.float32)
                    self.transcribe_job_q.put(("wake", recent))
                    self.last_wake_submit = now

                # --------------------------------------------
                # Handle transcription results
                # --------------------------------------------
                while not self.transcribe_result_q.empty():
                    job_type, text = self.transcribe_result_q.get()

                    if job_type == "wake":
                        if self.state == "WAIT_WAKE" and heard_wake_word(text):
                            print(f"[wake heard] {text}")
                            self.begin_command_capture()

                    elif job_type == "command":
                        cleaned = strip_leading_wake_word(text)

                        # Pause mic while doing LLM + TTS so audio doesn't pile up
                        self.stop_stream()
                        clear_queue(self.audio_q)

                        try:
                            if cleaned:
                                self.handle_command(cleaned)
                            else:
                                print("[no command detected after wake word]")
                        finally:
                            clear_queue(self.audio_q)
                            self.ring.clear()
                            self.cooldown_until = time.time() + COOLDOWN_SEC
                            self.start_stream()
                            self.set_idle_listening()

                time.sleep(0.01)

        except KeyboardInterrupt:
            print("\nStopping assistant...")

        finally:
            self.shutdown()

    def shutdown(self):
        self.stop_event.set()

        try:
            self.transcribe_job_q.put_nowait(None)
        except queue.Full:
            pass

        try:
            self.stop_stream()
        except Exception:
            pass

        self.fish_serial.write(b'0')
        self.fish_serial.close()


# ============================================================
# ENTRY
# ============================================================
if __name__ == "__main__":
    assistant = FishAssistant()
    assistant.run()
