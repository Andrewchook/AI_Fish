import sounddevice as sd
import queue
import time
import whisper
from scipy.io.wavfile import write
import numpy as np
#from faster_whisper import WhisperModel

class STT_CPU():
    # -------- settings you may change
    DEVICE_SR = 44100        # sample rate of mic
    TARGET_SR = 16000        # Whisper expects 16k
    DURATION_SEC = 5        # record this many seconds
    WAV_PATH = "../media/audio.wav"
    MODEL_NAME = "base"      # try "tiny" first if slow on your Pi
    LANG = "en"
    # -------------------------------

	def __init__(self):
		self.sample_rate = 16000
		# Queue for audio stream
		self.q = queue.Queue()
        self.model_size = "base"
        self.wave_path="audio.wav"
        self.lang="en"


	def callback(self, indata, frames, time_info, status):
		# Put recorded audio into queue
		if status:
			print(status, file=sys.stderr)
		self.q.put(bytes(indata))

	def listen_to_stream(self)->str:
		stream = sd.RawInputStream(samplerate=self.sample_rate, blocksize=8000, dtype='int16', channels=1, callback=self.callback)
		stream.start()
		print('Starting audio stream....')
		start_time = time.time()
		wait_time = 5
		while time.time() < (start_time + wait_time): 
			pass
		stream.stop()
		stream.close()
		print('Stopping audio stream...')
		data = self.q.get()

    def record_audio(self,duration_sec: float) -> np.ndarray:
        """Record mono float32 audio at DEVICE_SR."""
        print(f"Recording {duration_sec:.1f}s...")
        audio = sd.rec(int(duration_sec * DEVICE_SR),
                       samplerate=DEVICE_SR,
                       channels=1,
                       dtype="float32")
        sd.wait()
        return audio[:, 0]
    
    def to_16k(self,audio: np.ndarray) -> np.ndarray:
        """Resample DEVICE_SR -> 16k float32."""
        if DEVICE_SR == TARGET_SR:
            return audio.astype(np.float32)
        return resample_poly(audio, TARGET_SR, DEVICE_SR).astype(np.float32)
    
    def write_wav_16k(self,path: str, audio_16k: np.ndarray):
        """Write 16k mono WAV int16."""
        pcm16 = np.clip(audio_16k, -1.0, 1.0)
        pcm16 = (pcm16 * 32767.0).astype(np.int16)
    
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # int16
            wf.setframerate(TARGET_SR)
            wf.writeframes(pcm16.tobytes())

    def transcribe(path: str) -> str:
        model = whisper.load_model(MODEL_NAME)
        t0 = time.time()
        result = model.transcribe(
            path,
            language=LANG,
            fp16=False,                 # for CPU on Raspberry Pi
            verbose=False,
            temperature=0.0,
            condition_on_previous_text=False,
        )
        dt = time.time() - t0
        text = (result.get("text") or "").strip()
        print(f"Transcription time: {dt:.2f}s")
        return text


