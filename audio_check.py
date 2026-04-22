import os
import time
import speech_recognition as sr
import azure.cognitiveservices.speech as speechsdk
from dotenv import load_dotenv

load_dotenv()

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
    print("\n--- 🔊 SPEAKER & AZURE VOICE TEST ---")
    speech_config = speechsdk.SpeechConfig(
        subscription=os.getenv("AZURE_SPEECH_KEY"), 
        region=os.getenv("AZURE_SPEECH_REGION")
    )
    
    # You can change the voice in your .env file!
    voice_name = os.getenv("AZURE_SPEECH_VOICE", "en-US-DavisNeural")
    speech_config.speech_synthesis_voice_name = voice_name
    
    audio_config = speechsdk.audio.AudioOutputConfig(use_default_speaker=True)
    synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
    
    text = f"Hello ARIA framework! I am currently using the Azure voice named {voice_name}. If you can hear me, your speakers are working perfectly."
    print(f"Synthesizing Voice: {voice_name}")
    print(f"Text: '{text}'\n")
    
    result = synthesizer.speak_text_async(text).get()
    
    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        print("✅ Speaker test completed successfully!")
    else:
        print(f"❌ Speaker test failed. Reason: {result.reason}")
        if result.reason == speechsdk.ResultReason.Canceled:
            cancellation_details = result.properties.get(speechsdk.PropertyId.SpeechServiceResponse_JsonErrorDetails)
            print(f"Error details: {cancellation_details}")

if __name__ == "__main__":
    print("Welcome to the ARIA Audio Setup.")
    test_microphone()
    time.sleep(1)
    test_speakers()
    print("\n=============================================")
    print("If both tests passed, you are ready for the End-to-End loop!")
