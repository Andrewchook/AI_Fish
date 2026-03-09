from __future__ import annotations

import sys
from pathlib import Path
import time
import wave
import numpy as np


class STT_HAILO:
    """
    Drop-in STT module that uses Hailo's hailo-apps Whisper pipeline.

    Uses:
      app/hailo_whisper_pipeline.py: HailoWhisperPipeline
        - send_data(data)
        - get_transcription()
        - stop()

    You provide:
      - raw mono audio samples OR a wav file
    """

    def __init__(
        self,
        speech_recognition_dir: str = "~/CPE542/hailo-apps/hailo_apps/python/standalone_apps/speech_recognition",
        variant: str = "base",  # "tiny" or "base"
        hw_arch: str = "h8",    # matches your folder app/hefs/h8/...
        host: str = "arm64",
    ):
        self.variant = variant
        self.host = host

        self.speech_recognition_dir = Path(speech_recognition_dir).expanduser().resolve()
        if not (self.speech_recognition_dir / "app").exists():
            raise FileNotFoundError(f"Expected {self.speech_recognition_dir}/app to exist")

        # Make hailo-apps speech_recognition importable (so 'import app.xxx' works)
        if str(self.speech_recognition_dir) not in sys.path:
            sys.path.insert(0, str(self.speech_recognition_dir))

        # Import the pipeline class
        from app.hailo_whisper_pipeline import HailoWhisperPipeline

        # Locate HEFs (based on your screenshot + hailo_stt.py structure)
        hefs_dir = self.speech_recognition_dir / "app" / "hefs" / hw_arch / self.variant
        if not hefs_dir.exists():
            raise FileNotFoundError(f"HEFs dir not found: {hefs_dir}")

        # Your base files looked like:
        #   base-whisper-encoder-5s.hef
        #   base-whisper-decoder-fixed-sequence-matmul-split.hef
        encoder_hef = next(hefs_dir.glob(f"{self.variant}-whisper-encoder-*.hef"), None)
        decoder_hef = next(hefs_dir.glob(f"{self.variant}-whisper-decoder-*.hef"), None)

        if encoder_hef is None:
            raise FileNotFoundError(f"Could not find encoder hef in {hefs_dir}")
        if decoder_hef is None:
            raise FileNotFoundError(f"Could not find decoder hef in {hefs_dir}")

        self.encoder_hef = str(encoder_hef)
        self.decoder_hef = str(decoder_hef)

        # Create the pipeline
        # Signature from your grep:
        #   __init__(encoder_model_path, decoder_model_path, variant="tiny", host="arm64")
        self.pipeline = HailoWhisperPipeline(
            encoder_model_path=self.encoder_hef,
            decoder_model_path=self.decoder_hef,
            variant=self.variant,
            host=self.host,
        )

    def close(self):
        """Stop and release pipeline resources."""
        try:
            self.pipeline.stop()
        except Exception:
            pass

    # ---------- Convenience helpers ----------

    @staticmethod
    def _read_wav_mono_float32(wav_path: str) -> tuple[np.ndarray, int]:
        """
        Read a WAV file and return (samples_float32_mono, sample_rate).
        Converts int16 PCM to float32 in [-1,1].
        If stereo, it averages channels to mono.
        """
        wav_path = str(Path(wav_path).expanduser().resolve())
        with wave.open(wav_path, "rb") as wf:
            sr = wf.getframerate()
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            n_frames = wf.getnframes()
            raw = wf.readframes(n_frames)

        if sampwidth != 2:
            raise ValueError(f"Expected 16-bit PCM WAV (sampwidth=2). Got sampwidth={sampwidth}")

        audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        if n_channels == 2:
            audio = audio.reshape(-1, 2).mean(axis=1)  # stereo -> mono
        elif n_channels != 1:
            raise ValueError(f"Unsupported channel count: {n_channels}")

        return audio, sr

    # ---------- Main API you’ll use ----------

    def transcribe_wav(self, wav_path: str, timeout_s: float = 15.0) -> dict:
        """
        Send a WAV file to the pipeline and return {"text": "..."}.

        The hailo pipeline handles:
          - resampling/feature extraction (internally)
          - encoder/decoder NPU inference
          - tokenization/decoding

        We just:
          - load audio
          - send_data
          - poll get_transcription (or wait briefly)
        """
        audio, sr = self._read_wav_mono_float32(wav_path)

        # NOTE: send_data(data) signature isn't explicit about expected format.
        # Most Whisper pipelines accept float32 PCM samples.
        # We'll send a dict with audio+sr if it supports it, else raw audio.
        sent = False
        last_err = None

        for payload in (
            {"audio": audio, "sample_rate": sr},
            {"data": audio, "sample_rate": sr},
            audio,
        ):
            try:
                self.pipeline.send_data(payload)
                sent = True
                break
            except Exception as e:
                last_err = e

        if not sent:
            raise RuntimeError(
                "Failed to send audio to HailoWhisperPipeline.send_data(). "
                "The pipeline's send_data signature likely expects a specific payload.\n"
                f"Last error: {last_err}"
            )

        # Wait for transcription
        t0 = time.time()
        while True:
            try:
                text = self.pipeline.get_transcription()
                # Some implementations return "" until ready; some return None.
                if text:
                    return {"text": text}
            except Exception:
                # If it throws while not ready, keep polling until timeout.
                pass

            if (time.time() - t0) > timeout_s:
                return {"text": ""}

            time.sleep(0.05)