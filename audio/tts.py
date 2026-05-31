import asyncio
import ctypes
import logging
import os
import tempfile
import threading
import uuid

import edge_tts

logger = logging.getLogger("ARIA.TTS")

DEFAULT_VOICE = "en-GB-RyanNeural"


def _resolve_voice() -> str:
    return (
        os.getenv("EDGE_VOICE")
        or os.getenv("AZURE_SPEECH_VOICE")
        or DEFAULT_VOICE
    )


async def _synthesize_to_file(text: str, voice: str, out_path: str) -> None:
    communicator = edge_tts.Communicate(text, voice=voice)
    await communicator.save(out_path)


def _run_async(coro_factory):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro_factory())

    result_container = {}
    error_container = {}

    def runner():
        try:
            result_container["value"] = asyncio.run(coro_factory())
        except Exception as exc:
            error_container["error"] = exc

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    thread.join()

    if "error" in error_container:
        raise error_container["error"]
    return result_container.get("value")


if os.name == "nt":
    _winmm = ctypes.WinDLL("winmm")

    def _mci_send(command: str) -> str:
        buffer = ctypes.create_unicode_buffer(256)
        error = _winmm.mciSendStringW(command, buffer, len(buffer), 0)
        if error:
            err_buffer = ctypes.create_unicode_buffer(256)
            _winmm.mciGetErrorStringW(error, err_buffer, len(err_buffer))
            raise RuntimeError(f"MCI error {error}: {err_buffer.value}")
        return buffer.value

    def _play_mp3(path: str) -> None:
        alias = f"aria_tts_{uuid.uuid4().hex}"
        _mci_send(f'open "{path}" type mpegvideo alias {alias}')
        try:
            _mci_send(f"play {alias} wait")
        finally:
            _mci_send(f"close {alias}")
else:
    def _play_mp3(path: str) -> None:
        raise RuntimeError("MCI playback is only supported on Windows.")


def speak(text: str) -> None:
    if not text or not text.strip():
        return

    voice = _resolve_voice()
    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp.close()

    try:
        _run_async(lambda: _synthesize_to_file(text, voice, tmp.name))
        _play_mp3(tmp.name)
    except Exception as e:
        logger.error(f"TTS speak() failed: {e}")
        print(f"  [!] TTS error: {e}")
    finally:
        try:
            os.remove(tmp.name)
        except Exception:
            pass


def speak_to_file(text: str) -> str:
    """
    Generates speech and writes to a temp MP3 file.
    Returns the file path. Used by Discord voice channel playback.
    """
    if not text or not text.strip():
        return ""

    voice = _resolve_voice()
    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp.close()

    try:
        _run_async(lambda: _synthesize_to_file(text, voice, tmp.name))
        return tmp.name
    except Exception as e:
        logger.error(f"TTS speak_to_file() failed: {e}")
        try:
            os.remove(tmp.name)
        except Exception:
            pass
        raise
