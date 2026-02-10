import pvporcupine

class wake_word: 
    def __init__(self):
        API_KEY = load_api_key()
        print("API key loaded successfully")
        print(API_KEY)
        porcupine = pvporcupine.create(
            access_key=API_KEY,
            keyword_paths=['/home/fish/CPE542/AI_Fish/media/Hey-fish_en_raspberry-pi_v4_0_0.ppn']
            )

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

