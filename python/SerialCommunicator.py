import os
import serial


class SerialCommunicator:
    def __init__(self, port=None, baud=9600, timeout=1):
        self.ser = None
        port = port or os.getenv("TEENSY_PORT", "/dev/ttyACM0")
        try:
            self.ser = serial.Serial(port, baudrate=baud, timeout=timeout)
            print(f"Serial connected to {port} @ {baud}")
        except Exception as e:
            print(f"Warning: could not open serial port {port}: {e}")
            self.ser = None

    def send_state(self, state: int):
        if self.ser and self.ser.is_open:
            try:
                # send single byte (0,1,2)
                self.ser.write(bytes([int(state) & 0xFF]))
                self.ser.flush()
            except Exception as e:
                print("Serial send error:", e)
        else:
            # no-op when serial unavailable
            pass

    def close(self):
        if self.ser and self.ser.is_open:
            try:
                self.ser.close()
            except Exception:
                pass