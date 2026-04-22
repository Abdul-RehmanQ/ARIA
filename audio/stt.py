import os
import wave
import pyaudio
import keyboard
from groq import Groq

client = Groq(api_key=os.getenv("GROQ_API_KEY"))


def _transcribe_with_groq(file_path, upload_name=None):
    filename = upload_name or os.path.basename(file_path)
    with open(file_path, "rb") as audio_file:
        transcription = client.audio.transcriptions.create(
            file=(filename, audio_file.read()),
            model="whisper-large-v3-turbo",
            response_format="text"
        )
    return transcription.strip()


def transcribe_audio_file(file_path):
    if not file_path or not os.path.exists(file_path):
        print("[-] Ears (STT) Error: audio file path is invalid.")
        return None

    try:
        return _transcribe_with_groq(file_path)
    except Exception as e:
        print(f"[-] Ears (STT) Error: {e}")
        return None

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
        return _transcribe_with_groq(temp_filename, "temp_audio.wav")
    except Exception as e:
        print(f"[-] Ears (STT) Error: {e}")
        return None
    finally:
        if os.path.exists(temp_filename):
            os.remove(temp_filename)
