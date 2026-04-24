import os
import json
import traceback
import logging
from groq import Groq
import actions.system_ops as ops

logger = logging.getLogger("ARIA.Brain")

# ──────────────────────────────────────────────────────────────────────────────
# Groq client — validated at import time so we fail loudly, not silently.
# ──────────────────────────────────────────────────────────────────────────────
_groq_api_key = os.getenv("GROQ_API_KEY")
if not _groq_api_key:
    raise EnvironmentError(
        "GROQ_API_KEY is not set in your .env file. "
        "The LLM brain cannot function without it."
    )

client = Groq(api_key=_groq_api_key)

USERNAME = os.getlogin()
HOME_DIR = os.path.expanduser("~")
DESKTOP_DIR = os.path.join(HOME_DIR, "Desktop")

SYSTEM_PROMPT = f"""You are ARIA, a highly intelligent and professional AI assistant. 
You are currently providing verbal responses directly to the user's audio speakers.

CRITICAL RULES:
1. KEEP YOUR RESPONSES EXTREMELY SHORT AND CONCISE. (1 to 3 sentences maximum).
2. DO NOT use markdown symbols like asterisks (*) or hashes (#) because the Text-to-Speech audio engine will literally read them out loud. However, you MAY use newlines/line breaks to format lists cleanly on the screen.
3. Be polite, direct, and slightly formal but friendly.

SYSTEM INFO:
- The user's Windows Username is: {USERNAME}
- The user's Home Directory is: {HOME_DIR}
- The user's Desktop path is: {DESKTOP_DIR}
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
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "take_screenshot",
            "description": "Takes a screenshot of the user's monitor and saves it to their PC. Call this when they ask to take a screenshot or picture of the screen.",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False
            }
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
                "required": ["city_name"],
                "additionalProperties": False
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
                "required": ["app_name"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "close_application",
            "description": "Forcefully closes or quits a native Windows application.",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {
                        "type": "string",
                        "description": "The name of the application to close, e.g. chrome, notepad, spotify"
                    }
                },
                "required": ["app_name"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "play_spotify_media",
            "description": "Plays music on Spotify. Can play a specific track, an album, a public playlist, or the user's personal 'Liked Songs'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The name of the song, album, or playlist. If playing liked songs, just pass 'liked songs'."
                    },
                    "media_type": {
                        "type": "string",
                        "enum": ["track", "album", "playlist", "liked_songs"],
                        "description": "The type of media to play."
                    }
                },
                "required": ["query", "media_type"],
                "additionalProperties": False
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
                "required": ["command"],
                "additionalProperties": False
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
                "required": ["volume_percent"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "Lists all folders and files inside a specific directory on the PC's hard drive.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The absolute Windows path of the folder to look inside (e.g., 'C:\\' or 'D:\\Projects'). Always use absolute paths."
                    }
                },
                "required": ["path"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Reads the text contents of a specific file on the PC.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The absolute Windows path to the text file you want to read."
                    }
                },
                "required": ["path"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_file",
            "description": "Creates a new text file or overwrites an existing one anywhere on the PC.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The absolute Windows path where the file should be created (e.g., 'D:\\Notes\\hello.txt')."
                    },
                    "content": {
                        "type": "string",
                        "description": "The exact text content to write inside the file."
                    }
                },
                "required": ["path", "content"],
                "additionalProperties": False
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
    "close_application": ops.close_application,
    "play_spotify_media": ops.play_spotify_media,
    "control_spotify": ops.control_spotify,
    "change_system_volume": ops.change_system_volume,
    "list_directory": ops.list_directory,
    "read_file": ops.read_file,
    "create_file": ops.create_file
}

# We keep a rolling history so it remembers the conversation
chat_history = [
    {"role": "system", "content": SYSTEM_PROMPT}
]

def safe_chat_completion(messages, tools_list=None, tool_choice_val=None):
    """A hybrid router that cascades through multiple models if rate limits are hit."""
    # List of available Groq models in order of preference and intelligence
    models = [
        "llama-3.3-70b-versatile",
        "meta-llama/llama-4-scout-17b-16e-instruct",
        "llama-3.1-8b-instant",
        "mixtral-8x7b-32768",
        "gemma2-9b-it"
    ]
    
    kwargs = {
        "messages": messages,
        "max_tokens": 2048
    }
    
    if tools_list:
        kwargs["tools"] = tools_list
        kwargs["tool_choice"] = tool_choice_val
        # NOTE: parallel_tool_calls is intentionally omitted.
        # Groq's llama-3.3-70b rejects it with a failed_generation error,
        # which causes the entire request to fall back to text-only mode
        # and ARIA just hallucinates the action instead of executing it.
        
    for model in models:
        kwargs["model"] = model
        try:
            return client.chat.completions.create(**kwargs)
        except Exception as e:
            error_str = str(e).lower()

            # ── Rate limit: swap to next model ───────────────────────────
            if "429" in error_str or "rate limit" in error_str or "tokens per day" in error_str or "tokens per minute" in error_str:
                print(f"  [!] Model '{model}' Rate Limit Reached. Swapping to next model...")
                logger.warning(f"Rate limit on model '{model}'. Trying next. Error: {e}")
                continue

            # ── Tool call rejected: skip to next model WITH tools still on ──────
            # IMPORTANT: do NOT fall back to text-only here — that causes ARIA to
            # hallucinate the action ("Spotify is opening!") without actually doing it.
            if tools_list and ("tool_use_failed" in error_str or "failed_generation" in error_str):
                print(f"  [!] Model '{model}' rejected a tool call. Trying next model...")
                logger.warning(f"Tool call rejected by '{model}'. Skipping to next model. Error: {e}")
                continue  # Try the next model in the list with tools still active

            # ── Auth error: no point trying other models ──────────────────
            if "401" in error_str or "authentication" in error_str or "invalid api key" in error_str:
                logger.error(f"Groq API key is invalid or expired: {e}")
                raise ConnectionError(
                    "Your GROQ_API_KEY is invalid or expired. "
                    "Please update it in your .env file."
                ) from e

            # ── Network error: no point trying other models ───────────────
            if "connection" in error_str or "timeout" in error_str or "network" in error_str:
                logger.error(f"Network error contacting Groq API: {e}")
                raise ConnectionError(
                    "Could not reach the Groq API. Please check your internet connection."
                ) from e

            # ── Anything else: surface it immediately ─────────────────────
            logger.error(f"Groq API error on model '{model}': {e}\n{traceback.format_exc()}")
            raise e

    # All models exhausted their rate limits
    raise Exception(
        "Critical: ALL Groq models have exhausted their rate limits. "
        "Please wait a few minutes for tokens to refill."
    )

def ask_aria(user_input, update_callback=None):
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

            executed_tool_outputs = []
            seen_tool_invocations = set()
            
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

                    try:
                        invocation_key = (
                            function_name,
                            json.dumps(function_args, sort_keys=True)
                        )
                    except Exception:
                        invocation_key = (function_name, str(function_args))

                    if invocation_key in seen_tool_invocations:
                        continue
                    seen_tool_invocations.add(invocation_key)

                    if update_callback:
                        try:
                            update_callback(f"Executing: {function_name}...")
                        except Exception:
                            # Keep local execution resilient even if external listeners fail.
                            pass
                        
                    print(f"  [⚡ Executing System Tool: {function_name}({function_args})]")

                    # ── Execute the tool — isolated so one crash can't kill the whole response ──
                    try:
                        function_response = function_to_call(**function_args)
                        print(f"  [✓ Tool Output: {str(function_response)[:200]}]")
                    except TypeError as e:
                        # Wrong arguments were passed — the LLM sent bad params
                        logger.error(
                            f"Tool '{function_name}' received invalid arguments {function_args}: {e}"
                        )
                        function_response = (
                            f"Error: '{function_name}' was called with invalid arguments. "
                            f"Details: {e}"
                        )
                        print(f"  [✗ Tool '{function_name}' argument error: {e}]")
                    except Exception as e:
                        logger.error(
                            f"Tool '{function_name}' raised an exception: {e}\n"
                            f"{traceback.format_exc()}"
                        )
                        function_response = (
                            f"Error: The system action '{function_name}' failed. "
                            f"Reason: {e}"
                        )
                        print(f"  [✗ Tool '{function_name}' failed: {e}]")

                    # 3. Tell the AI the result (or error) of the physical action
                    chat_history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": function_name,
                        "content": str(function_response),
                    })
                    executed_tool_outputs.append({
                        "name": function_name,
                        "content": str(function_response),
                    })
                
            # 4. Have the LLM read the outputs and form a final conversational reply
            synthesis_messages = chat_history
            if executed_tool_outputs:
                synthesis_messages = chat_history + [{
                    "role": "system",
                    "content": (
                        "Use the tool outputs above as the source of truth. "
                        "Do not claim that you lack real-time access, web access, or browsing access "
                        "when tool outputs are present. Keep your answer concise and directly grounded "
                        "in the latest relevant tool result."
                    )
                }]

            final_response = safe_chat_completion(messages=synthesis_messages)
            
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
            
    except ConnectionError as e:
        # Network or auth errors — specific, actionable message
        logger.error(f"Brain (LLM) Connection Error: {e}")
        print(f"[-] Brain (LLM) Connection Error: {e}")
        return "I'm unable to reach my cloud reasoning engine right now, sir. Please check your internet connection and API keys."

    except MemoryError:
        # Conversation history is too large — clear it and recover
        logger.error("Brain (LLM) MemoryError: Conversation history too large. Resetting.")
        print("[-] Brain (LLM) Memory Overflow: Conversation history was too large. Resetting memory.")
        chat_history.clear()
        chat_history.append({"role": "system", "content": SYSTEM_PROMPT})
        return "My conversation memory has been reset due to overflow, sir. Please repeat your request."

    except Exception as e:
        logger.error(f"Brain (LLM) unhandled error: {e}\n{traceback.format_exc()}")
        print(f"[-] Brain (LLM) Error: {type(e).__name__}: {e}")
        # If chat_history got corrupted during the error, trim the last bad entry
        try:
            if chat_history and chat_history[-1].get("role") == "user":
                chat_history.pop()
                logger.info("Brain: Removed corrupt/orphaned user message from history.")
        except Exception:
            pass
        return "I'm sorry, sir. I encountered an internal error. Please try your request again."
