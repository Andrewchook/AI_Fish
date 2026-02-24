import pyaudio
import queue
import time
import whisper
import numpy as np
from scipy.signal import resample_poly
import sounddevice as sd

#from faster_whisper import WhisperModel

SAMPLE_RATE = 16000
DURATION=5

class STT_CPU():
    def __init__(self):
        # Queue for audio stream
        self.q = queue.Queue()
        self.model_size = "base"
        self.wave_path="audio.wav"
        self.lang="en"

    def listen_to_stream(self,audio_model)->str:
        print('Listening...')
        audio = sd.rec(int(DURATION * SAMPLE_RATE),
               samplerate=SAMPLE_RATE,
               channels=1,
               dtype='float32')

        sd.wait()
        print("Recording finished.")

        # Flatten to 1D array
        audio = np.squeeze(audio)
        result = audio_model.transcribe(audio,verbose=True,fp16=False)
        print("audio transcribed")
        return result
