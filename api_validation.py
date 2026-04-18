import os
import sys
import requests
from dotenv import load_dotenv

import google.generativeai as genai
import cohere
from groq import Groq
import azure.cognitiveservices.speech as speechsdk

# Force load the .env in current directory
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

def run_validation():
    print("=== JARVIS API AUTHENTICATION VALIDATION ===")
    all_passed = True
    
    # 1. Google Gemini
    try:
        gemini_key = os.getenv("GEMINI_API_KEY")
        if not gemini_key:
            raise ValueError("No Gemini key found in .env")
        genai.configure(api_key=gemini_key)
        list(genai.list_models())
        print("[+] Google Gemini API: Authentication Successful")
    except Exception as e:
        print(f"[-] Google Gemini API: FAILED - {e}")
        all_passed = False

    # 2. Cohere
    try:
        co = cohere.Client(os.getenv("COHERE_API_KEY"))
        co.chat(message="ping", max_tokens=1)
        print("[+] Cohere API: Authentication Successful")
    except Exception as e:
        print(f"[-] Cohere API: FAILED - {e}")
        all_passed = False

    # 3. Groq
    try:
        groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        groq_client.models.list()
        print("[+] Groq API: Authentication Successful")
    except Exception as e:
        print(f"[-] Groq API: FAILED - {e}")
        all_passed = False

    # 4. OpenRouter
    try:
        headers = {"Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}"}
        res = requests.get("https://openrouter.ai/api/v1/auth/key", headers=headers)
        if res.status_code == 200:
            print("[+] OpenRouter API: Authentication Successful")
        else:
            print(f"[-] OpenRouter API: FAILED - Status {res.status_code}")
            all_passed = False
    except Exception as e:
        print(f"[-] OpenRouter API: FAILED - {e}")
        all_passed = False

    # 5. Azure Speech
    try:
        speech_config = speechsdk.SpeechConfig(
            subscription=os.getenv("AZURE_SPEECH_KEY"), 
            region=os.getenv("AZURE_SPEECH_REGION")
        )
        if speech_config:
            print("[+] Azure Speech API: Configuration verified successfully")
    except Exception as e:
        print(f"[-] Azure Speech API: FAILED - {e}")
        all_passed = False

    print("\n=============================================")
    if all_passed:
        print("[SUCCESS] ALL APIs ARE WORKING AND READY FOR JARVIS!")
    else:
        print("[WARNING] SOME APIs FAILED. PLEASE CHECK THE ERRORS ABOVE.")

if __name__ == "__main__":
    run_validation()
