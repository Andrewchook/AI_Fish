import whisper
import time

start_time = time.time()
model = whisper.load_model("base")
model_time = time.time()
result = model.transcribe("media/You Shall Not Pass!.mp3")
result_time = time.time()


print(result["text"])
print(f'Time to load model: %d s', (model_time - start_time))
print(f'Time to run model: %d s', (result_time - model_time))

