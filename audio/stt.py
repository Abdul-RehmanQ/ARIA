import os
import wave
import pyaudio
import keyboard
import speech_recognition as sr
from groq import Groq

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
recognizer = sr.Recognizer()

# Dynamically adjust energy threshold so he hears quiet voices
recognizer.energy_threshold = 300 
recognizer.dynamic_energy_threshold = True

def record_manual_push_to_talk():
    """Fallback manual recording triggered when Spacebar is held down."""
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 44100
    
    p = pyaudio.PyAudio()
    temp_filename = "temp_audio.wav"
    
    stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
    frames = []
    
    print("\n🎙️ Recording Manual Override... (Release SPACEBAR to stop)")
    while keyboard.is_pressed('space'):
        try:
            data = stream.read(CHUNK, exception_on_overflow=False)
            frames.append(data)
        except Exception:
            pass
            
    print("✅ Recording stopped. Processing via Groq Whisper...")
    stream.stop_stream()
    stream.close()
    p.terminate()
    
    if len(frames) < 10:
        return None
        
    wf = wave.open(temp_filename, 'wb')
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(p.get_sample_size(FORMAT))
    wf.setframerate(RATE)
    wf.writeframes(b''.join(frames))
    wf.close()
    
    try:
        with open(temp_filename, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                file=("temp_audio.wav", audio_file.read()),
                model="whisper-large-v3-turbo", 
                response_format="text"
            )
        if os.path.exists(temp_filename):
            os.remove(temp_filename)
        return transcription.strip()
    except Exception as e:
        print(f"[-] Ears (STT) Error: {e}")
        return None

def listen_and_transcribe():
    """Hybrid Listening Mode: Continuously listens for 'Jarvis' wake-word, OR manual spacebar override."""
    
    print("\n[Press SPACEBAR to talk directly, OR just say 'Jarvis' out loud...]")
    
    # We load the microphone once inside the loop
    with sr.Microphone() as source:
        # Loop forever until either spacebar is pressed OR wake-word is heard
        while True:
            # 1. Check for manual Spacebar Override
            if keyboard.is_pressed('space'):
                return record_manual_push_to_talk()
                
            # 2. Wake-Word Listening Phase
            try:
                # We listen in tiny 0.5s chunks so the loop doesn't get permanently blocked
                # phrase_time_limit restricts recording to 5 seconds max if it hears talking
                audio = recognizer.listen(source, timeout=0.5, phrase_time_limit=5)
                
                # Audio detected! Send to Tier-1 (Free Google Engine) to check for Wake-Word
                try:
                    text = recognizer.recognize_google(audio).lower()
                    
                    if "jarvis" in text:
                        print(f"\n[🔔 Wake-Word Heard]: {text}")
                        print("✅ Routing to Groq Whisper for precise transcription...")
                        
                        # Save the audio chunk to a file
                        temp_filename = "temp_wake.wav"
                        with open(temp_filename, "wb") as f:
                            f.write(audio.get_wav_data())
                            
                        # Send the exact same audio file to Tier-2 (Groq Whisper)
                        try:
                            with open(temp_filename, "rb") as audio_file:
                                transcription = client.audio.transcriptions.create(
                                    file=("temp_wake.wav", audio_file.read()),
                                    model="whisper-large-v3-turbo", 
                                    response_format="text"
                                )
                            if os.path.exists(temp_filename):
                                os.remove(temp_filename)
                            return transcription.strip()
                        except Exception as e:
                            print(f"[-] Groq API Error: {e}")
                            return None
                            
                except sr.UnknownValueError:
                    # Heard background noise but no legible words
                    pass
                except sr.RequestError:
                    # Internet offline
                    pass
                    
            except sr.WaitTimeoutError:
                # No audio detected in the 0.5s window. The loop safely restarts so it can check keyboard.is_pressed('space') again!
                pass
