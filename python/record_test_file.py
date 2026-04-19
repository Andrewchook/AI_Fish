# record audio and save to a file in ../meida/audio.wav
import sounddevice as sd
import numpy as np
import wave
duration: int = 5
sample_rate: int = 16000
filename="../media/audio.wav"
print(f"Recording audio for {duration} seconds...")
audio = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype='int16')
sd.wait()  # Wait until recording is finished
print(f"Recording finished. Saving to {filename}...")
with wave.open(filename, 'wb') as wf:
    wf.setnchannels(1)  # Mono
    wf.setsampwidth(2)  # 16 bits per sample
    wf.setframerate(sample_rate)
    wf.writeframes(audio.tobytes())
print(f"Audio saved to {filename}")
