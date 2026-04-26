import os
import re
import json
import asyncio
import inspect
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

from actions.system_ops import tools as agent_tools
from actions.mcp_tools import load_mcp_tools

# Load any configured MCP servers before grabbing schemas
load_mcp_tools()

class SessionMemory:
    def __init__(self, session_id="aria_main", db_path=os.path.join("memory", "aria_memory.json")):
        self.db_path = db_path
        self.history = []
        self._load()

    def _load(self):
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, "r", encoding="utf-8") as f:
                    self.history = json.load(f)
            except Exception:
                pass

    def _save(self):
        try:
            with open(self.db_path, "w", encoding="utf-8") as f:
                json.dump(self.history, f)
        except Exception:
            pass

    def add(self, message):
        self.history.append(message)
        self._save()

    def get_memory(self):
        return self.history

    def clear(self):
        self.history.clear()
        self._save()

tools = agent_tools.get_json_schemas()

memory = SessionMemory(session_id="aria_main", db_path=os.path.join("memory", "aria_memory.json"))
if not memory.get_memory():
    memory.add({"role": "system", "content": SYSTEM_PROMPT})

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
    global memory
    
    # Append the user's message
    memory.add({"role": "user", "content": user_input})
    
    try:
        # 1. Ask the AI if it wants to use a tool or just reply directly
        response = safe_chat_completion(
            messages=memory.get_memory(),
            tools_list=tools,
            tool_choice_val="auto"
        )
        
        response_message = response.choices[0].message
        
        # 2. Check if the AI decided to call a tool!
        if response_message.tool_calls:
            # We must append the AI's tool request to history first
            memory.add(response_message.model_dump(exclude_unset=True))

            executed_tool_outputs = []
            seen_tool_invocations = set()
            
            # We process each tool call (it might try to do multiple things at once)
            for tool_call in response_message.tool_calls:
                function_name = tool_call.function.name
                
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
                    # Resolve callables from the shared toolkit first (includes MCP tools),
                    # then fall back to local module functions for legacy compatibility.
                    registered_tool = agent_tools.tools.get(function_name)
                    function_to_call = None
                    if registered_tool and getattr(registered_tool, "original_func", None):
                        function_to_call = registered_tool.original_func
                    else:
                        function_to_call = getattr(ops, function_name)

                    function_response = function_to_call(**function_args)
                    if inspect.isawaitable(function_response):
                        function_response = asyncio.run(function_response)

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
                memory.add({
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
            synthesis_messages = memory.get_memory()
            if executed_tool_outputs:
                synthesis_messages = memory.get_memory() + [{
                    "role": "system",
                    "content": (
                        "Use the tool outputs above as the source of truth. "
                        "Do not claim that you lack real-time access, web access, or browsing access "
                        "when tool outputs are present. Keep your answer concise and directly grounded "
                        "in the latest relevant tool result."
                    )
                }]

            final_response = safe_chat_completion(messages=synthesis_messages)
            
            final_text = final_response.choices[0].message.content or ""
            # Strip hallucinated XML tags that reasoning/fallback models inject.
            # 1. <think>...</think> or <thinking>...</thinking>
            final_text = re.sub(r'<think(?:ing)?>.*?</think(?:ing)?>', '', final_text, flags=re.DOTALL)
            # 2. <function=...></function> (Groq tool hallucinations)
            final_text = re.sub(r'<function=.*?</function>', '', final_text, flags=re.DOTALL)
            final_text = final_text.strip()
            
            # Save strictly as a dict for standard appending
            memory.add({"role": "assistant", "content": final_text})
            return final_text
            
        else:
            # If no tools were used, just return the standard text reply
            reply_text = response_message.content or ""
            # Strip any leaked reasoning tags from direct replies too
            reply_text = re.sub(r'<think(?:ing)?>.*?</think(?:ing)?>', '', reply_text, flags=re.DOTALL)
            reply_text = re.sub(r'<function=.*?</function>', '', reply_text, flags=re.DOTALL)
            reply_text = reply_text.strip()
            memory.add({"role": "assistant", "content": reply_text})
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
        memory.clear()
        memory.add({"role": "system", "content": SYSTEM_PROMPT})
        return "My conversation memory has been reset due to overflow, sir. Please repeat your request."

    except Exception as e:
        logger.error(f"Brain (LLM) unhandled error: {e}\n{traceback.format_exc()}")
        print(f"[-] Brain (LLM) Error: {type(e).__name__}: {e}")
        return "I'm sorry, sir. I encountered an internal error. Please try your request again."
