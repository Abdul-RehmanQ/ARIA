import os
import sys
import traceback
import logging
from datetime import datetime
from dotenv import load_dotenv

# ──────────────────────────────────────────────────────────────────────────────
# LOGGING SETUP — Writes all errors to 'aria_errors.log' AND the console.
# ──────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.ERROR,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
          logging.FileHandler(os.path.join("logs", "aria_errors.log"), encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("ARIA")

# ──────────────────────────────────────────────────────────────────────────────
# STEP 1: Load environment variables BEFORE importing any submodule.
# ──────────────────────────────────────────────────────────────────────────────
env_path = os.path.join(os.path.dirname(__file__), ".env")
if not os.path.exists(env_path):
    logger.error("FATAL: '.env' file not found. Please create it with the required API keys.")
    sys.exit(1)

load_dotenv(env_path)

# ──────────────────────────────────────────────────────────────────────────────
# STEP 2: Validate that all required API keys are present before proceeding.
# ──────────────────────────────────────────────────────────────────────────────
REQUIRED_ENV_KEYS = [
    "GROQ_API_KEY",
    "AZURE_SPEECH_KEY",
    "AZURE_SPEECH_REGION",
]

missing_keys = [key for key in REQUIRED_ENV_KEYS if not os.getenv(key)]
if missing_keys:
    logger.error(
        f"FATAL: The following required keys are missing from your .env file: "
        f"{', '.join(missing_keys)}"
    )
    sys.exit(1)

# ──────────────────────────────────────────────────────────────────────────────
# STEP 3: Import core modules — catch any import-time failures cleanly.
# ──────────────────────────────────────────────────────────────────────────────
try:
    from audio.stt import listen_and_transcribe
except ImportError as e:
    logger.error(f"FATAL: Could not import STT module (audio/stt.py): {e}")
    logger.error("Tip: Run 'pip install -r requirements.txt' to install missing packages.")
    sys.exit(1)

try:
    from audio.tts import speak
except ImportError as e:
    logger.error(f"FATAL: Could not import TTS module (audio/tts.py): {e}")
    logger.error("Tip: Run 'pip install -r requirements.txt' to install missing packages.")
    sys.exit(1)

try:
    from brain.llm_router import ask_aria
except ImportError as e:
    logger.error(f"FATAL: Could not import Brain module (brain/llm_router.py): {e}")
    sys.exit(1)
                                        
# ──────────────────────────────────────────────────────────────────────────────
# MAIN LOOP
# ──────────────────────────────────────────────────────────────────────────────
def main():
    print("\n" + "=" * 60)
    print("                       ARIA IS ONLINE")
    print("=" * 60)
    print(f"  Session started: {datetime.now().strftime('%A, %B %d, %Y at %I:%M %p')}")
    print(f"  Error log: logs/aria_errors.log")
    print("=" * 60)

    greeting = "Systems initialized. I am online and ready, sir."
    print(f"ARIA: {greeting}")

    # Speak the greeting — don't crash if TTS fails at startup
    try:
        speak(greeting)
    except Exception as e:
        logger.error(f"TTS failed during startup greeting: {e}")
        print("  [!] Voice synthesis unavailable at startup. Continuing in text-only mode.")

    print("\n(To safely quit ARIA, press Ctrl+C in this terminal)")

    # ── Main conversation loop ─────────────────────────────────────────────
    consecutive_errors = 0
    MAX_CONSECUTIVE_ERRORS = 5  # Prevent infinite silent-failure loops

    while True:
        try:
            # ── Listen ────────────────────────────────────────────────────
            try:
                user_text = listen_and_transcribe()
            except OSError as e:
                logger.error(f"Microphone/Audio device error: {e}")
                print(f"\n[!] Microphone Error: Could not access your audio device. ({e})")
                print("    Please check that your microphone is plugged in and try again.")
                consecutive_errors += 1
                if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                    print(f"\n[✗] ARIA has encountered {MAX_CONSECUTIVE_ERRORS} consecutive errors.")
                    print("    Shutting down to prevent further issues. Check 'logs/aria_errors.log'.")
                    break
                continue
            except Exception as e:
                logger.error(f"Unexpected STT error: {e}\n{traceback.format_exc()}")
                print(f"\n[!] Ears (STT) failed unexpectedly: {e}")
                consecutive_errors += 1
                continue

            # ── Validate transcription ────────────────────────────────────
            if not user_text or not user_text.strip():
                # Not an error — user just tapped space or there was silence.
                consecutive_errors = 0
                continue

            consecutive_errors = 0  # Reset error counter on any successful input
            print(f"\nYou: {user_text}")

            # ── Think ─────────────────────────────────────────────────────
            try:
                response = ask_aria(user_text)
            except MemoryError:
                logger.error("MemoryError: Conversation history may be too large.")
                response = "I'm sorry, sir. My memory is overloaded. Let me reset."
                # Attempt to clear history to recover
                try:
                    from brain.llm_router import chat_history, SYSTEM_PROMPT
                    chat_history.clear()
                    chat_history.append({"role": "system", "content": SYSTEM_PROMPT})
                    print("  [✓] Conversation memory cleared and reset successfully.")
                except Exception:
                    pass
            except Exception as e:
                logger.error(f"Brain (LLM) error while processing: '{user_text}'\n{e}\n{traceback.format_exc()}")
                response = "I've encountered an internal error, sir. Please try your request again."

            print(f"ARIA: {response}\n")

            # ── Speak ─────────────────────────────────────────────────────
            try:
                speak(response)
            except Exception as e:
                # TTS failure is non-fatal — response was already printed to console.
                logger.error(f"TTS failed while speaking response: {e}")
                print(f"  [!] Voice output failed. Response displayed above in text.")

        except KeyboardInterrupt:
            # ── Graceful shutdown via Ctrl+C ──────────────────────────────
            print("\n\n" + "=" * 60)
            print("  Shutdown signal received (Ctrl+C).")
            shutdown_msg = "Shutting down protocols. Goodbye for now, sir."
            print(f"ARIA: {shutdown_msg}")
            try:
                speak(shutdown_msg)
            except Exception:
                pass  # Don't block shutdown if TTS is broken
            print("=" * 60)
            # Ensure any background threads (keyboard listeners, audio, etc.) can't keep
            # the process alive by forcing an exit after attempting graceful shutdown.
            try:
                import os
                os._exit(0)
            except Exception:
                break

        except Exception as e:
            # ── Catch-all: any completely unexpected crash ────────────────
            logger.error(
                f"[CRITICAL] Unhandled exception in main loop:\n"
                f"{traceback.format_exc()}"
            )
            print(f"\n[✗] Unexpected System Error: {type(e).__name__}: {e}")
            print("    ARIA is recovering and will continue listening...")
            print("    (Full error details saved to 'logs/aria_errors.log')")
            consecutive_errors += 1
            if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                print(f"\n[✗] ARIA has encountered {MAX_CONSECUTIVE_ERRORS} consecutive unrecoverable errors.")
                print("    Shutting down. Please check 'logs/aria_errors.log' for details.")
                try:
                    import os
                    os._exit(1)
                except Exception:
                    break


if __name__ == "__main__":
    main()
