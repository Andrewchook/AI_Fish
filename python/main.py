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
from google.genai import types
#from openai import OpenAI


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

#initialize serial communication with teensy
PORT = "/dev/ttyACM0"   # adjust if needed
BAUD = 9600

ser = serial.Serial(PORT, BAUD, timeout=1)

# --- initialization ---
#load whisper model
start_time = time.time()
model = whisper.load_model("base")
model_time = time.time()
print(f'Time to load model: %d s', (model_time - start_time))

client = genai.Client(api_key=get_api_key("../media/gemini_api_key.txt"))

api_key = get_api_key("../media/elevenLabs_key.txt")
eleven_labs_client = ElevenLabs(
    api_key=api_key
)

# --- Porpupine Wake Word ---
#wait for the wake word to be heard
#calls porcupine API
print("Listening for wake word.")
ser.write(b'1')   #flap tail to indicate "listening for wake word"
wake_word.start_listening()

# --- Whisper STT ---
#activate whisper to listen for speech
#run locally on cpu right now
print("Listening for speech.")
ser.write(b'2')   #lift head to indicate "listening"
result = stt_model.listen_to_stream(model,ser)
print(result["text"])

# --- LLM ---
ser.write(b'1')   #flap tail to indicate "thinking"
response = client.models.generate_content(
    model="gemini-3-flash-preview", 
    contents=result["text"],
    config=types.GenerateContentConfig(
        system_instruction=
        """
        You are a witty fish on the wall. 
        Make really smart remarks.
        Keep responses to roughly 20 words.
        Keep the grammar simple.
        """
    )
)
print(response.text)

# --- TTS ---
ser.write(b'1')   #flap tail to indicate "thinking"
audio_stream = eleven_labs_client.text_to_speech.convert(
    # text=response.text
    text=response.text,
    voice_id="Bj9UqZbhQsanLzgalpEG",
    model_id="eleven_multilingual_v2",
    output_format="mp3_44100_128",
)
ser.write(b'3')  #speak response
play(audio_stream)

ser.write(b'0')   #do nothing (idle)
ser.close()
