import queue
import threading
import time
import re
from collections import deque

import numpy as np
import sounddevice as sd
import whisper


# =========================
# Config
# =========================
SAMPLE_RATE = 16000
MODEL_NAME = "tiny.en"        # start here for speed; try "base.en" later
WAKE_WORD = "fish"

WAKE_WINDOW_SEC = 1.2         # size of chunk sent to Whisper for wake listening
WAKE_STEP_SEC = 0.35          # how often to send a new overlapping wake chunk
PRE_ROLL_SEC = 0.6            # audio kept before wake detection so you don't lose first words

COMMAND_MAX_SEC = 6.0         # hard cap for command recording
SILENCE_HOLD_SEC = 0.9        # end command after this much silence
VOICE_RMS_THRESHOLD = 0.015   # tune for your mic/noise floor
COOLDOWN_SEC = 1.0            # prevents immediate retrigger


# =========================
# Helpers
# =========================
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


# =========================
# Queues
# =========================
audio_q = queue.Queue()
transcribe_job_q = queue.Queue(maxsize=1)
transcribe_result_q = queue.Queue()


# =========================
# Audio callback
# =========================
def audio_callback(indata, frames, time_info, status):
    if status:
        print(status)
    # mono float32 in [-1, 1]
    audio_q.put(indata[:, 0].copy())


# =========================
# Whisper worker
# =========================
def transcribe_worker(model_name: str):
    print(f"Loading Whisper model: {model_name}")
    model = whisper.load_model(model_name)
    print("Whisper model loaded.")

    while True:
        job = transcribe_job_q.get()
        if job is None:
            break

        job_type, audio = job

        try:
            result = model.transcribe(
                audio,
                language="en",
                fp16=False,
                verbose=False,
            )
            text = result.get("text", "").strip()
        except Exception as e:
            text = ""
            print(f"[transcribe error] {e}")

        transcribe_result_q.put((job_type, text))


# =========================
# Command handler
# =========================
def handle_command(text: str):
    print(f"\n[COMMAND] {text}\n")
    # Put your Gemini / ElevenLabs / serial logic here.


def start_wake_listener():
    main()

# =========================
# Main loop
# =========================
def main():
    worker = threading.Thread(
        target=transcribe_worker,
        args=(MODEL_NAME,),
        daemon=True,
    )
    worker.start()

    blocksize = int(0.05 * SAMPLE_RATE)   # 50 ms frames
    wake_samples = int(WAKE_WINDOW_SEC * SAMPLE_RATE)
    preroll_samples = int(PRE_ROLL_SEC * SAMPLE_RATE)
    max_command_samples = int(COMMAND_MAX_SEC * SAMPLE_RATE)
    silence_hold_samples = int(SILENCE_HOLD_SEC * SAMPLE_RATE)

    ring = deque(maxlen=wake_samples + preroll_samples)

    state = "WAIT_WAKE"  # WAIT_WAKE, RECORD_COMMAND, WAIT_COMMAND_TRANSCRIPT
    last_wake_submit = 0.0
    cooldown_until = 0.0

    command_chunks = []
    command_samples = 0
    silence_samples = 0
    speech_started = False

    print("Opening microphone stream...")
    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
        blocksize=blocksize,
        callback=audio_callback,
    ):
        print("Listening continuously... say 'fish'")

        while True:
            # -------------------------
            # Drain audio queue quickly
            # -------------------------
            drained_any = False
            while True:
                try:
                    frame = audio_q.get(timeout=0.02 if not drained_any else 0.0)
                    drained_any = True
                except queue.Empty:
                    break

                ring.extend(frame)

                if state == "RECORD_COMMAND":
                    command_chunks.append(frame.copy())
                    command_samples += len(frame)

                    frame_rms = rms(frame)

                    if frame_rms > VOICE_RMS_THRESHOLD:
                        speech_started = True
                        silence_samples = 0
                    elif speech_started:
                        silence_samples += len(frame)

                    hit_max_len = command_samples >= max_command_samples
                    hit_silence = speech_started and (silence_samples >= silence_hold_samples)

                    if hit_max_len or hit_silence:
                        full_command_audio = np.concatenate(command_chunks).astype(np.float32)

                        if transcribe_job_q.empty():
                            transcribe_job_q.put(("command", full_command_audio))
                            state = "WAIT_COMMAND_TRANSCRIPT"
                            print("[transcribing full command...]")

            # -------------------------
            # Submit overlapping wake chunks
            # -------------------------
            now = time.time()
            if (
                state == "WAIT_WAKE"
                and now >= cooldown_until
                and len(ring) >= wake_samples
                and (now - last_wake_submit) >= WAKE_STEP_SEC
                and transcribe_job_q.empty()
            ):
                recent = np.array(list(ring)[-wake_samples:], dtype=np.float32)
                transcribe_job_q.put(("wake", recent))
                last_wake_submit = now

            # -------------------------
            # Read transcription results
            # -------------------------
            while not transcribe_result_q.empty():
                job_type, text = transcribe_result_q.get()

                if job_type == "wake":
                    if state == "WAIT_WAKE" and heard_wake_word(text):
                        print(f"[wake heard] {text}")

                        pre = np.array(list(ring)[-preroll_samples:], dtype=np.float32)

                        command_chunks = [pre]
                        command_samples = len(pre)
                        silence_samples = 0
                        speech_started = False
                        state = "RECORD_COMMAND"

                        print("[recording command...]")

                elif job_type == "command":
                    cleaned = strip_leading_wake_word(text)

                    if cleaned:
                        handle_command(cleaned)
                    else:
                        print("[no command detected after wake word]")

                    command_chunks = []
                    command_samples = 0
                    silence_samples = 0
                    speech_started = False

                    state = "WAIT_WAKE"
                    cooldown_until = time.time() + COOLDOWN_SEC
                    print("Listening continuously... say 'fish'")

            time.sleep(0.01)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopping...")
        try:
            transcribe_job_q.put_nowait(None)
        except queue.Full:
            pass
