import whisper
import time
from wake_word import *
import sounddevice as sd
from stt_cpu import *
from elevenlabs import stream
from elevenlabs.client import ElevenLabs
from google import genai

from openai import OpenAI


def get_api_key(file_path):
    try:
        with open(file_path) as f:
            api_key = f.readline().strip()
        return api_key

    except FileNotFoundError: 
        print(f"Error: the file {file_path}  was not found")

wake_word=wake_word()
stt_model = STT_CPU()

# --- initialization ---
#load whisper model
start_time = time.time()
model = whisper.load_model("base")
model_time = time.time()
print(f'Time to load model: %d s', (model_time - start_time))

client = genai.Client(api_key=get_api_key("../media/gemini_api_key.txt"))

messages = [
    {"role": "system", "content": "You are a witty fish on the wall. "
                                  "Make really smart remarks. "},
    {"role": "system", "content": "Keep responses to roughly 20 words"},
]

api_key = get_api_key("../media/elevenLabs_key.txt")
eleven_labs_client = ElevenLabs(
    api_key=api_key
)

while True:
    try:
        # --- Porpupine Wake Word ---
        #wait for the wake word to be heard
        #calls porcupine API
        print("Listening for wake word.")
        wake_word.start_listening()

        # --- Whisper STT ---
        #activate whisper to listen for speech
        #run locally on cpu right now
<<<<<<< HEAD
        print("Listening for speech.")
        result = stt_model.listen_to_stream(model)
        print(result["text"])
=======
        audio = stt_model.record_audio(DURATION_SEC)
        audio_16k = stt_model.to_16k(audio)
        stt_model.write_wav_16k(WAV_PATH, audio_16k)
        #stt_model.listen_to_stream()
        # --- LLM ---
>>>>>>> refs/remotes/origin/main

        # --- LLM ---
        response = client.models.generate_content(
            model="gemini-3-flash-preview", contents=result["text"]
        )
        print(response.text)

        # --- TTS ---
        audio_stream = eleven_labs_client.text_to_speech.convert(
            text=response.text,
            voice_id="FF6KdobWPaiR0vkcALHF",
            model_id="eleven_multilingual_v1",
            voice_settings={
                "stability": -1.8,
                "similarity_boost": -1.8
            },
            seed=59999
        )

    except (KeyboardInterrupt):
       print("stopping...")

