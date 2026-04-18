import os
from groq import Groq

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# We instruct the AI exactly how to behave when speaking verbally.
SYSTEM_PROMPT = """You are Jarvis, a highly intelligent and professional AI assistant. 
You are currently providing verbal responses directly to the user's audio speakers.

CRITICAL RULES:
1. KEEP YOUR RESPONSES EXTREMELY SHORT AND CONCISE. (1 to 3 sentences maximum, unless asked to explain something).
2. DO NOT output markdown, bullet points, asterisks, emojis, or code blocks. Audio systems cannot read markdown. Use perfectly natural, conversational plain English.
3. Be polite, direct, and slightly formal but friendly.
"""

def ask_jarvis(user_input):
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_input}
            ]
        )
        return completion.choices[0].message.content
    except Exception as e:
        print(f"[-] Brain (LLM) Error: {e}")
        return "I'm sorry, sir. I'm currently unable to connect to my central processing servers."
