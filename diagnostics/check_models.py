import os
from dotenv import load_dotenv
import requests

load_dotenv('.env')

def _print_models(label, url, api_key):
    if not api_key:
        print(f"[{label}] Missing API key.")
        return

    try:
        response = requests.get(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=20,
        )
        print(f"[{label}] {response.status_code}")
        print(response.text)
    except Exception as exc:
        print(f"[{label}] Error: {exc}")


_print_models(
    "Groq",
    "https://api.groq.com/openai/v1/models",
    os.getenv("GROQ_API_KEY"),
)
