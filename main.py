import os
from dotenv import load_dotenv

# MUST LOAD .env FIRST before importing the submodules so they have access to API keys!
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from audio.stt import listen_and_transcribe
from audio.tts import speak
from brain.llm_router import ask_jarvis

def main():
    print("\n" + "="*60)
    print("                      JARVIS IS ONLINE")
    print("="*60)
    
    greeting = "Systems initialized. I am online and ready, sir."
    print(f"Jarvis: {greeting}")
    speak(greeting)
    print("\n(To safely quit Jarvis, press Ctrl+C in this terminal)")
    
    while True:
        try:
            # The Push-To-Talk mechanism completely handles blocking here now.
            user_text = listen_and_transcribe()
            
            if not user_text or user_text.strip() == "":
                continue
                
            print(f"\nYou: {user_text}")
            
            # Send the transcribed text strictly to the Llama 3 Brain
            response = ask_jarvis(user_text)
            
            print(f"Jarvis: {response}\n")
            
            # Output the text as audio
            speak(response)
            
        except KeyboardInterrupt:
            print("\nShutting down Jarvis...")
            speak("Shutting down protocols. Goodbye for now.")
            break
        except Exception as e:
            print(f"\n[-] Unexpected System Error: {e}")

if __name__ == "__main__":
    main()
