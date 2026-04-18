import os
import azure.cognitiveservices.speech as speechsdk

def speak(text):
    try:
        speech_config = speechsdk.SpeechConfig(
            subscription=os.getenv("AZURE_SPEECH_KEY"), 
            region=os.getenv("AZURE_SPEECH_REGION")
        )
        
        # Load voice setting from .env
        voice_name = os.getenv("AZURE_SPEECH_VOICE", "en-GB-RyanNeural")
        speech_config.speech_synthesis_voice_name = voice_name
        
        audio_config = speechsdk.audio.AudioOutputConfig(use_default_speaker=True)
        synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
        
        result = synthesizer.speak_text_async(text).get()
        
        if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
            print(f"[-] Mouth (TTS) Error: {result.reason}")
    except Exception as e:
        print(f"[-] Speech Synthesis Error: {e}")
