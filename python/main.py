import whisper
import time
from wake_word import *
import sounddevice as sd
from stt_cpu import *

wake_word=wake_word()
stt_model = STT_CPU()

# --- initialization ---
#load whisper model
start_time = time.time()
model = whisper.load_model("base")
model_time = time.time()
print(f'Time to load model: %d s', (model_time - start_time))

while True:
    try:
        # --- Porpupine Wake Word ---
        #wait for the wake word to be heard
        #calls porcupine API
        wake_word.start_listening()
       
        # --- Whisper STT ---
        #activate whisper to listen for speech
        #run locally on cpu right now
        audio = stt_model.record_audio(DURATION_SEC)
        audio_16k = stt_model.to_16k(audio)
        stt_model.write_wav_16k(WAV_PATH, audio_16k)
        #stt_model.listen_to_stream()
        # --- LLM ---


        # --- TTS ---

    except (KeyboardInterrupt):
       print("stopping...")

