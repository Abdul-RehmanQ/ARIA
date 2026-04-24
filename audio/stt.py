import os
import wave
import traceback
import logging
import pyaudio
import keyboard
from groq import Groq

logger = logging.getLogger("ARIA.STT")

# ──────────────────────────────────────────────────────────────────────────────
# Initialise the Groq client — validate the key is present first.
# ──────────────────────────────────────────────────────────────────────────────
_groq_api_key = os.getenv("GROQ_API_KEY")
if not _groq_api_key:
    raise EnvironmentError(
        "GROQ_API_KEY is not set in your .env file. "
        "STT (speech-to-text) will not work without it."
    )

client = Groq(api_key=_groq_api_key)


def _transcribe_with_groq(file_path, upload_name=None):
    """Internal helper: sends an audio file to Groq Whisper and returns the transcript."""
    filename = upload_name or os.path.basename(file_path)
    with open(file_path, "rb") as audio_file:
        transcription = client.audio.transcriptions.create(
            file=(filename, audio_file.read()),
            model="whisper-large-v3-turbo",
            response_format="text"
        )
    return transcription.strip()


def transcribe_audio_file(file_path):
    """Public helper: transcribes an audio file at the given path."""
    if not file_path or not os.path.exists(file_path):
        logger.error(f"STT: Audio file path is invalid or missing: '{file_path}'")
        return None

    try:
        return _transcribe_with_groq(file_path)
    except FileNotFoundError:
        logger.error(f"STT: Audio file disappeared before it could be transcribed: '{file_path}'")
        return None
    except Exception as e:
        logger.error(f"STT: Groq transcription failed: {e}\n{traceback.format_exc()}")
        print(f"[-] Ears (STT) Error: {e}")
        return None


def listen_and_transcribe():
    """
    Blocks until the user holds SPACEBAR, records audio, and returns the
    transcribed text. Returns None on silence, empty audio, or any failure.
    """
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 44100
    temp_filename = "temp_audio.wav"

    print("\n[Hold down the SPACEBAR to speak...]")

    # ── Wait for SPACEBAR press ─────────────────────────────────────────────
    try:
        keyboard.wait('space')
    except Exception as e:
        logger.error(f"STT: Keyboard listener failed — cannot detect SPACEBAR: {e}")
        print(f"[-] Keyboard Error: {e}")
        return None

    # ── Open audio stream ───────────────────────────────────────────────────
    p = None
    stream = None
    try:
        p = pyaudio.PyAudio()
        stream = p.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK
        )
    except OSError as e:
        logger.error(f"STT: Could not open microphone stream: {e}")
        print(f"\n[-] Microphone Error: Could not open audio input device.")
        print(f"    Detail: {e}")
        if p:
            try:
                p.terminate()
            except Exception:
                pass
        return None
    except Exception as e:
        logger.error(f"STT: Unexpected error initialising PyAudio: {e}\n{traceback.format_exc()}")
        print(f"[-] Audio System Error: {e}")
        if p:
            try:
                p.terminate()
            except Exception:
                pass
        return None

    print("\n🎙️  Recording... (Release SPACEBAR to stop)")

    # ── Record while SPACEBAR is held ───────────────────────────────────────
    frames = []
    try:
        while keyboard.is_pressed('space'):
            try:
                data = stream.read(CHUNK, exception_on_overflow=False)
                frames.append(data)
            except OSError as e:
                # Buffer overflow or device error — skip the chunk and keep going
                logger.error(f"STT: Audio chunk read error (skipping): {e}")
                continue
    except Exception as e:
        logger.error(f"STT: Recording loop failed: {e}\n{traceback.format_exc()}")
        print(f"[-] Recording Error: {e}")
    finally:
        # Always clean up the audio stream, even if recording errored mid-way
        try:
            stream.stop_stream()
            stream.close()
        except Exception:
            pass
        try:
            p.terminate()
        except Exception:
            pass

    print("✅ Recording stopped. Processing...")

    # ── Ignore accidental taps ──────────────────────────────────────────────
    if len(frames) < 10:
        return None

    # ── Write audio frames to temp WAV file ────────────────────────────────
    try:
        wf = wave.open(temp_filename, 'wb')
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(p.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))
        wf.close()
    except Exception as e:
        logger.error(f"STT: Failed to write temporary audio file: {e}\n{traceback.format_exc()}")
        print(f"[-] Audio File Error: Could not save recorded audio for processing. ({e})")
        return None

    # ── Transcribe with Groq Whisper ────────────────────────────────────────
    try:
        result = _transcribe_with_groq(temp_filename, "temp_audio.wav")
        return result
    except ConnectionError as e:
        logger.error(f"STT: No internet connection for Groq Whisper API: {e}")
        print("[-] Network Error: Could not reach Groq. Please check your internet connection.")
        return None
    except Exception as e:
        error_str = str(e).lower()
        if "401" in error_str or "authentication" in error_str or "invalid api key" in error_str:
            logger.error(f"STT: Groq API key is invalid or expired: {e}")
            print("[-] Auth Error: Your GROQ_API_KEY appears to be invalid or expired.")
        elif "429" in error_str or "rate limit" in error_str:
            logger.error(f"STT: Groq Whisper rate limit hit: {e}")
            print("[-] Rate Limit: Groq Whisper quota exceeded. Please wait a moment.")
        else:
            logger.error(f"STT: Groq transcription error: {e}\n{traceback.format_exc()}")
            print(f"[-] Ears (STT) Error: {e}")
        return None
    finally:
        # Always delete the temp file — even if transcription failed
        if os.path.exists(temp_filename):
            try:
                os.remove(temp_filename)
            except Exception as e:
                logger.error(f"STT: Could not delete temp audio file '{temp_filename}': {e}")
