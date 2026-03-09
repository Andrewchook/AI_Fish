import queue
import time
import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000
DEVICE_SR = 44100 
DURATION = 5


class STT_CPU:
    def __init__(self, sample_rate: int = SAMPLE_RATE, duration: int = DURATION):
        self.sample_rate = sample_rate
        self.duration = duration
        self.q = queue.Queue()

    def record_audio(self,duration_sec: float) -> np.ndarray:
        """Record mono float32 audio at DEVICE_SR."""
        print(f"Recording {duration_sec:.1f}s...")
        audio = sd.rec(int(duration_sec * DEVICE_SR),
                       samplerate=DEVICE_SR,
                       channels=1,
                       dtype="float32")
        sd.wait()
        return audio[:, 0]
        
    def listen_to_stream(self, audio_model) -> dict:
        """Record audio for `self.duration` seconds and transcribe with `audio_model`.

        Returns the raw transcription result (dict) returned by Whisper.
        """
        print("Listening...")
        audio = sd.rec(int(self.duration * self.sample_rate),
                       samplerate=self.sample_rate,
                       channels=1,
                       dtype="float32")
        sd.wait()
        print("Recording finished.")

        # Flatten to 1D array
        audio = np.squeeze(audio)
        # Whisper's `transcribe` accepts a numpy array or path depending on model wrapper.
        result = audio_model.transcribe(audio, verbose=True, fp16=False, language="en")
        print("Audio transcribed")
        return result

