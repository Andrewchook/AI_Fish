import whisper
import time
import os
from wake_word import *
import sounddevice as sd
from stt_cpu import *
from elevenlabs import stream
from elevenlabs.client import ElevenLabs
from google import genai
from elevenlabs.play import play
import serial
from SerialCommunicator import SerialCommunicator


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
DURATION_SEC = 5

# create communicator (port can be overridden with TEENSY_PORT env var)
serial_comm = SerialCommunicator()
serial_comm.send_state(0)

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

# --- Porpupine Wake Word ---
#wait for the wake word to be heard
#calls porcupine API
print("Listening for wake word.")
serial_comm.send_state(1)
wake_word.start_listening()

# --- Whisper STT ---
#activate whisper to listen for speech
#run locally on cpu right now
print("Listening for speech.")
serial_comm.send_state(1)
result = stt_model.listen_to_stream(model)
print(result["text"])
# --- LLM ---

# --- LLM ---
response = client.models.generate_content(
    model="gemini-3-flash-preview", contents=result["text"]
)
print(response.text)

# --- TTS ---
serial_comm.send_state(2)
audio_stream = eleven_labs_client.text_to_speech.convert(
    # text=response.text
    text=response.text,
    voice_id="JBFqnCBsd6RMkjVDRZzb",
    model_id="eleven_multilingual_v2",
    output_format="mp3_44100_128",
)
play(audio_stream)

serial_comm.send_state(0)
serial_comm.close()
