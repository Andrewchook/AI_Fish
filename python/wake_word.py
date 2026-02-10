import pvporcupine
import pyaudio
import struct

class wake_word: 
    def __init__(self):
        API_KEY = load_api_key()
        print("API key loaded successfully")
        print(API_KEY)
        porcupine = pvporcupine.create(
            access_key=API_KEY,
            keyword_paths=['/home/fish/CPE542/AI_Fish/media/Hey-fish_en_raspberry-pi_v4_0_0.ppn']
            )
        self.pa = pyaudio.PyAudio()
        self.audio_stream = self.pa.open(
                rate=self.porcupine.sample_rate,
                channels=1,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=self.porcupine.frame_length
                )
    
    def start_listening(self):
        try:
            while True:
                #read audio from input
                pcm = self.audio_stream.read(self.porcupine.frame_length)
                pcm_unpacked = struct.unpack_from("h" * self.porcupine.frame_length,pcm)

                #pass audio to porc
                result= self.porcupine.process(pcm_unpacked)

                if result>=0:
                    print("Wake word detected")
                    break
        except KeyboardInterrupt:
            print("Stopping..")

        finally:
            self.cleanup()

    def cleanup(self):
        self.audio_stream.close()
        self.pa.terminate()
        self.porcupine.delete()

def load_api_key(file_path="/home/fish/CPE542/AI_Fish/media/picovoice_key.txt"):
    try:
        with open(file_path, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        raise FileNotFoundError(f"API key file not found: {file_path}")
    except Exception as e:
        raise RuntimeError(f"Error reading API key: {e}")


if __name__ == '__main__':
	wake_word = wake_word()

