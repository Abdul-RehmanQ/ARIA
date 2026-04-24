import os
import io
import wave
import threading
import traceback
import logging
import pyaudio
import azure.cognitiveservices.speech as speechsdk

logger = logging.getLogger("ARIA.TTS")

# Global lock to prevent overlapping voices
speak_lock = threading.Lock()


def speak(text):
    """
    Synthesises the given text to speech via Azure and plays it synchronously
    through PyAudio. All errors are caught and logged — TTS failure is always
    non-fatal so ARIA continues running even if the voice goes down.
    """
    if not text or not text.strip():
        # Nothing to say — skip silently
        return

    # ── Validate Azure credentials before making any API call ──────────────
    azure_key = os.getenv("AZURE_SPEECH_KEY")
    azure_region = os.getenv("AZURE_SPEECH_REGION")

    if not azure_key or not azure_region:
        missing = []
        if not azure_key:
            missing.append("AZURE_SPEECH_KEY")
        if not azure_region:
            missing.append("AZURE_SPEECH_REGION")
        logger.error(
            f"TTS: Cannot synthesise speech — missing environment variables: "
            f"{', '.join(missing)}"
        )
        print(f"[-] TTS Config Error: {', '.join(missing)} not found in .env file.")
        return

    with speak_lock:
        # ── Configure Azure Speech ──────────────────────────────────────────
        try:
            speech_config = speechsdk.SpeechConfig(
                subscription=azure_key,
                region=azure_region
            )
            voice_name = os.getenv("AZURE_SPEECH_VOICE", "en-GB-RyanNeural")
            speech_config.speech_synthesis_voice_name = voice_name
        except Exception as e:
            logger.error(f"TTS: Failed to create Azure SpeechConfig: {e}\n{traceback.format_exc()}")
            print(f"[-] TTS Config Error: Could not initialise Azure Speech. ({e})")
            return

        # ── Synthesise the audio via Azure ──────────────────────────────────
        try:
            # audio_config=None streams raw audio back instead of playing it
            # through Azure's default device so we control exact playback timing.
            synthesizer = speechsdk.SpeechSynthesizer(
                speech_config=speech_config,
                audio_config=None
            )
            result = synthesizer.speak_text_async(text).get()
        except Exception as e:
            error_str = str(e).lower()
            if "401" in error_str or "authentication" in error_str:
                logger.error(f"TTS: Azure Speech API key is invalid or expired: {e}")
                print("[-] TTS Auth Error: Azure Speech API key is invalid or expired.")
            elif "connection" in error_str or "network" in error_str:
                logger.error(f"TTS: Network error connecting to Azure Speech: {e}")
                print("[-] TTS Network Error: Could not connect to Azure Speech. Check your internet.")
            else:
                logger.error(f"TTS: Azure speak_text_async() failed: {e}\n{traceback.format_exc()}")
                print(f"[-] TTS Synthesis Error: {e}")
            return

        # ── Check synthesis result ──────────────────────────────────────────
        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            audio_data = result.audio_data
        elif result.reason == speechsdk.ResultReason.Canceled:
            cancellation = result.cancellation_details
            if cancellation.reason == speechsdk.CancellationReason.Error:
                logger.error(
                    f"TTS: Azure synthesis cancelled due to error. "
                    f"Code: {cancellation.error_code}, Details: {cancellation.error_details}"
                )
                print(f"[-] TTS Cancelled: {cancellation.error_details}")
            else:
                logger.error(f"TTS: Azure synthesis cancelled. Reason: {cancellation.reason}")
                print(f"[-] TTS Cancelled: {cancellation.reason}")
            return
        else:
            logger.error(f"TTS: Unexpected synthesis result: {result.reason}")
            print(f"[-] TTS Error: Synthesis returned unexpected result: {result.reason}")
            return

        # ── Play the synthesised audio via PyAudio ──────────────────────────
        p = None
        stream = None
        try:
            f = io.BytesIO(audio_data)
            with wave.open(f, 'rb') as wf:
                p = pyaudio.PyAudio()
                stream = p.open(
                    format=p.get_format_from_width(wf.getsampwidth()),
                    channels=wf.getnchannels(),
                    rate=wf.getframerate(),
                    output=True
                )
                # Read and write in chunks — blocks until the speaker physically finishes
                chunk = wf.readframes(1024)
                while chunk:
                    stream.write(chunk)
                    chunk = wf.readframes(1024)

        except OSError as e:
            logger.error(f"TTS: Audio output device error during playback: {e}")
            print(f"[-] TTS Playback Error: Audio output device failed. ({e})")
        except Exception as e:
            logger.error(f"TTS: Unexpected error during audio playback: {e}\n{traceback.format_exc()}")
            print(f"[-] TTS Playback Error: {e}")
        finally:
            # Always release audio resources, even if playback errored mid-stream
            if stream:
                try:
                    stream.stop_stream()
                    stream.close()
                except Exception:
                    pass
            if p:
                try:
                    p.terminate()
                except Exception:
                    pass
