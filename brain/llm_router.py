import os
import json
from groq import Groq
import actions.system_ops as ops

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

SYSTEM_PROMPT = """You are Jarvis, a highly intelligent and professional AI assistant. 
You are currently providing verbal responses directly to the user's audio speakers.

CRITICAL RULES:
1. KEEP YOUR RESPONSES EXTREMELY SHORT AND CONCISE. (1 to 3 sentences maximum).
2. DO NOT output markdown, bullet points, asterisks, emojis, or code blocks. Audio systems cannot read markdown. Use perfectly natural plain English.
3. Be polite, direct, and slightly formal but friendly.
4. You have access to tools. If the user asks you to do something that a tool can do, USE THE TOOL.
5. Provide a short verbal response alongside your tool calls to acknowledge the action being taken.
6. NEVER manually type "<function=...>" tags in your text response. Use the tool calling API correctly.
"""

# ----------------------------------------------------
# THE BLUEPRINT: Telling Llama 3 what tools it has
# ----------------------------------------------------
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Returns the exact current date and time.",
        }
    },
    {
        "type": "function",
        "function": {
            "name": "take_screenshot",
            "description": "Takes a screenshot of the user's monitor and saves it to their PC. Call this when they ask to take a screenshot or picture of the screen.",
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Fetches the current weather for a specific city.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city_name": {
                        "type": "string",
                        "description": "The name of the city, e.g. New York, London, Islamabad"
                    }
                },
                "required": ["city_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_application",
            "description": "Opens a native Windows application or website.",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {
                        "type": "string",
                        "description": "The name of the application to open, e.g. chrome, notepad, spotify, youtube"
                    }
                },
                "required": ["app_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "play_spotify_music",
            "description": "Searches Spotify for a specific song and instantly starts playing it. Use this whenever the user asks to play a song or music.",
            "parameters": {
                "type": "object",
                "properties": {
                    "song_name": {
                        "type": "string",
                        "description": "The exact name of the song and artist. DO NOT use the word 'by' or any conversational filler. Format strictly as 'SongName ArtistName'"
                    }
                },
                "required": ["song_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "control_spotify",
            "description": "Controls the currently playing music on Spotify. Can pause, resume, skip tracks, go back, or change volume.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "enum": ["pause", "resume", "next", "previous", "volume"],
                        "description": "The playback command to execute."
                    },
                    "volume_percent": {
                        "type": "string",
                        "description": "If command is 'volume', the desired volume percentage from 0 to 100 as a string (e.g. '50')."
                    }
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "change_system_volume",
            "description": "Changes the main global Windows system volume of the PC. Use this when the user asks to change the laptop or PC volume, rather than just Spotify playback volume.",
            "parameters": {
                "type": "object",
                "properties": {
                    "volume_percent": {
                        "type": "string",
                        "description": "The desired volume percentage from 0 to 100 as a string (e.g. '100')."
                    }
                },
                "required": ["volume_percent"]
            }
        }
    }
]

# Map tool names to the actual python functions
available_functions = {
    "get_current_time": ops.get_current_time,
    "take_screenshot": ops.take_screenshot,
    "get_weather": ops.get_weather,
    "open_application": ops.open_application,
    "play_spotify_music": ops.play_spotify_music,
    "control_spotify": ops.control_spotify,
    "change_system_volume": ops.change_system_volume
}

# We keep a rolling history so it remembers the conversation
chat_history = [
    {"role": "system", "content": SYSTEM_PROMPT}
]

def safe_chat_completion(messages, tools_list=None, tool_choice_val=None):
    """A hybrid router that falls back to Llama 4 Scout if the 70B model exhausts its daily tokens."""
    primary_model = "llama-3.3-70b-versatile"
    fallback_model = "meta-llama/llama-4-scout-17b-16e-instruct"
    
    kwargs = {
        "model": primary_model,
        "messages": messages,
        "max_tokens": 2048
    }
    
    if tools_list:
        kwargs["tools"] = tools_list
        kwargs["tool_choice"] = tool_choice_val
        kwargs["parallel_tool_calls"] = False
        
    try:
        return client.chat.completions.create(**kwargs)
    except Exception as e:
        error_str = str(e).lower()
        if "429" in error_str or "rate limit" in error_str or "tokens per day" in error_str:
            print("  [!] 70B Model Daily Token Limit Reached. Auto-swapping to Llama 4 Scout...")
            kwargs["model"] = fallback_model
            return client.chat.completions.create(**kwargs)
        else:
            raise e

def ask_jarvis(user_input):
    global chat_history
    
    # Append the user's message
    chat_history.append({"role": "user", "content": user_input})
    
    try:
        # 1. Ask the AI if it wants to use a tool or just reply directly
        response = safe_chat_completion(
            messages=chat_history,
            tools_list=tools,
            tool_choice_val="auto"
        )
        
        response_message = response.choices[0].message
        
        # 2. Check if the AI decided to call a tool!
        if response_message.tool_calls:
            # We must append the AI's tool request to history first
            chat_history.append(response_message)
            
            # We process each tool call (it might try to do multiple things at once)
            for tool_call in response_message.tool_calls:
                function_name = tool_call.function.name
                function_to_call = available_functions.get(function_name)
                
                if function_to_call:
                    # Parse arguments
                    try:
                        args_str = tool_call.function.arguments
                        function_args = json.loads(args_str) if args_str else {}
                        if not isinstance(function_args, dict):
                            function_args = {}
                    except:
                        function_args = {}
                        
                    print(f"  [⚡ Executing System Tool: {function_name}({function_args})]")
                    
                    # Physically execute the python function on the PC!
                    function_response = function_to_call(**function_args)
                    
                    # 3. Tell the AI the result of the physical action
                    chat_history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": function_name,
                        "content": str(function_response),
                    })
                
            # 4. Have the LLM read the outputs and form a final conversational reply
            final_response = safe_chat_completion(messages=chat_history)
            
            import re
            final_text = final_response.choices[0].message.content
            # Hotfix: Forcefully delete any hallucinated JSON tags that Groq leaks out (with DOTALL to catch newlines)
            final_text = re.sub(r'<function=.*?</function>', '', final_text, flags=re.DOTALL).strip()
            
            # Save strictly as a dict for standard appending
            chat_history.append({"role": "assistant", "content": final_text})
            return final_text
            
        else:
            # If no tools were used, just return the standard text reply
            reply_text = response_message.content
            chat_history.append({"role": "assistant", "content": reply_text})
            return reply_text
            
    except Exception as e:
        print(f"[-] Brain (LLM) Error: {e}")
        return "I'm sorry, sir. I'm currently unable to process my system directives."
