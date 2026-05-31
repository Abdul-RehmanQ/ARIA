import os
import time
import speech_recognition as sr
from dotenv import load_dotenv

load_dotenv()

from audio.tts import speak

def test_microphone():
    print("\n--- 🎤 MICROPHONE TEST ---")
    recognizer = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            print("Listening! Please speak into your microphone for a few seconds...")
            recognizer.adjust_for_ambient_noise(source, duration=1)
            audio = recognizer.listen(source, timeout=10, phrase_time_limit=5)
            print(f"...Audio captured successfully! Got {len(audio.get_wav_data())} bytes of data.")
    except Exception as e:
        print(f"❌ Microphone test failed: {e}")
        print("Please check your Windows Privacy settings and ensure the microphone is allowed for Python.")

def test_speakers():
    print("\n--- 🔊 SPEAKER TEST ---")

    voice_name = os.getenv("EDGE_VOICE") or os.getenv("AZURE_SPEECH_VOICE") or "en-GB-RyanNeural"
    text = (
        "Hello ARIA framework! I am currently using the Edge voice named "
        f"{voice_name}. If you can hear me, your speakers are working perfectly."
    )

    print(f"Synthesizing Voice: {voice_name}")
    print(f"Text: '{text}'\n")

    try:
        speak(text)
        print("✅ Speaker test completed successfully!")
    except Exception as e:
        print(f"❌ Speaker test failed: {e}")

if __name__ == "__main__":
    print("Welcome to the ARIA Audio Setup.")
    test_microphone()
    time.sleep(1)
    test_speakers()
    print("\n=============================================")
    print("If both tests passed, you are ready for the End-to-End loop!")
