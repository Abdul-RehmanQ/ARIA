import os
import time
import logging
import numpy as np
import wave
import tempfile

logger = logging.getLogger("ARIA.TTS")

KOKORO_DIR = os.path.join(os.path.dirname(__file__), "kokoro")
MODEL_PATH = os.path.join(KOKORO_DIR, "kokoro-v1.0.int8.onnx")
VOICES_PATH = os.path.join(KOKORO_DIR, "voices-v1.0.bin")
SAMPLE_RATE = 24000  # Kokoro-82M native output rate

MODEL_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.int8.onnx"
VOICES_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin"


def _download_file(url: str, dest: str):
    import urllib.request
    import sys
    filename = os.path.basename(dest)
    print(f"  [v] Downloading {filename}...")
    try:
        def progress(count, block_size, total_size):
            if total_size > 0:
                percent = min(100, int(count * block_size * 100 / total_size))
                sys.stdout.write(f"\r      Downloading: {percent}%")
                sys.stdout.flush()
        urllib.request.urlretrieve(url, dest, reporthook=progress)
        print(f"\n  [OK] {filename} downloaded.")
    except Exception as e:
        # Remove partial file if download failed
        if os.path.exists(dest):
            try:
                os.remove(dest)
            except Exception:
                pass
        raise RuntimeError(f"Failed to download {filename}: {e}") from e


def _ensure_kokoro_files():
    os.makedirs(KOKORO_DIR, exist_ok=True)
    if not os.path.exists(MODEL_PATH):
        _download_file(MODEL_URL, MODEL_PATH)
    if not os.path.exists(VOICES_PATH):
        _download_file(VOICES_URL, VOICES_PATH)


# Module-level model instance — loaded once, reused across all calls
_kokoro = None

def _get_kokoro():
    global _kokoro
    if _kokoro is None:
        try:
            _ensure_kokoro_files()
            from kokoro_onnx import Kokoro
            _kokoro = Kokoro(MODEL_PATH, VOICES_PATH)
            logger.info("Kokoro TTS engine loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load Kokoro TTS: {e}")
            raise
    return _kokoro


def speak(text: str):
    if not text or not text.strip():
        return

    voice = os.getenv("KOKORO_VOICE", "af_heart")

    try:
        import sounddevice as sd
        kokoro = _get_kokoro()
        samples, sample_rate = kokoro.create(text, voice=voice, speed=1.0)
        # samples is float32 numpy array, sounddevice handles it natively
        sd.play(samples, samplerate=sample_rate)
        sd.wait()  # block until playback completes
    except Exception as e:
        logger.error(f"TTS speak() failed: {e}")
        print(f"  [!] TTS error: {e}")


def speak_to_file(text: str) -> str:
    """
    Generates speech and writes to a temp WAV file.
    Returns the file path. Used by Discord voice channel playback.
    """
    voice = os.getenv("KOKORO_VOICE", "af_heart")
    kokoro = _get_kokoro()
    samples, sample_rate = kokoro.create(text, voice=voice, speed=1.0)

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    with wave.open(tmp.name, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        # Convert float32 [-1, 1] to int16
        pcm = (samples * 32767).astype(np.int16)
        wf.writeframes(pcm.tobytes())

    return tmp.name
