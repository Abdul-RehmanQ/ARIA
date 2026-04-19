import os
import threading
import io
import wave
import pyaudio
import azure.cognitiveservices.speech as speechsdk

# Global lock to prevent overlapping voices
speak_lock = threading.Lock()

def speak(text):
    with speak_lock:
        try:
            speech_config = speechsdk.SpeechConfig(
                subscription=os.getenv("AZURE_SPEECH_KEY"), 
                region=os.getenv("AZURE_SPEECH_REGION")
            )
            
            voice_name = os.getenv("AZURE_SPEECH_VOICE", "en-GB-RyanNeural")
            speech_config.speech_synthesis_voice_name = voice_name
            
            # Request audio stream instead of playing it directly to default speaker
            # This prevents Azure from dumping audio into the OS buffer and releasing the lock prematurely!
            audio_config = None 
            synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
            
            result = synthesizer.speak_text_async(text).get()
            
            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                audio_data = result.audio_data
                
                # Play synchronously via PyAudio so the python thread is physically blocked until playback finishes
                f = io.BytesIO(audio_data)
                with wave.open(f, 'rb') as wf:
                    p = pyaudio.PyAudio()
                    stream = p.open(format=p.get_format_from_width(wf.getsampwidth()),
                                    channels=wf.getnchannels(),
                                    rate=wf.getframerate(),
                                    output=True)
                                    
                    data = wf.readframes(1024)
                    while data:
                        stream.write(data)
                        data = wf.readframes(1024)
                        
                    stream.stop_stream()
                    stream.close()
                    p.terminate()
            else:
                print(f"[-] Mouth (TTS) Error: {result.reason}")
                
        except Exception as e:
            print(f"[-] Speech Synthesis Error: {e}")
