import os
import wave
import pyaudio
import keyboard
from groq import Groq

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def listen_and_transcribe():
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 44100
    
    p = pyaudio.PyAudio()
    temp_filename = "temp_audio.wav"
    
    print("\n[Hold down the SPACEBAR to speak...]")
    
    # This completely halts the script until you press Space
    keyboard.wait('space')
    
    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK)
                    
    print("\n🎙️ Recording... (Release SPACEBAR to stop)")
    
    frames = []
    # Continuously record chunks of audio directly to RAM while space is held
    while keyboard.is_pressed('space'):
        try:
            data = stream.read(CHUNK, exception_on_overflow=False)
            frames.append(data)
        except Exception:
            pass
            
    print("✅ Recording stopped. Processing...")
    
    stream.stop_stream()
    stream.close()
    p.terminate()
    
    # If the user just tapped it accidentally, ignore it
    if len(frames) < 10:
        return None
        
    # Save frames to file
    wf = wave.open(temp_filename, 'wb')
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(p.get_sample_size(FORMAT))
    wf.setframerate(RATE)
    wf.writeframes(b''.join(frames))
    wf.close()
    
    # Stream the file securely to Groq Whisper for instant transcription
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
