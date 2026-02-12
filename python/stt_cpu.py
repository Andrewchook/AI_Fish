import sounddevice as sd
import queue
import time
import whisper
#from faster_whisper import WhisperModel

class STT_CPU():
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

    def transcribe(self):
