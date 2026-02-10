import whisper
import time

wake_word=wake_word()

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
        start_time = time.time()
        result = model.transcribe("../media/You Shall Not Pass!.mp3")
        result_time = time.time()

        print(result["text"])
        print(f'Time to run model: %d s', (result_time - model_time))

        # --- LLM ---


        # --- TTS ---

    except (KeyboardInterrupt):
       print("stopping...")

