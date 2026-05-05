import os
import re
import json
import asyncio
import inspect
import traceback
import logging
import getpass
import requests
from dotenv import load_dotenv
from groq import Groq
from openai import OpenAI
import actions.system_ops as ops
from brain.error_memory import error_memory

logger = logging.getLogger("ARIA.Brain")


class RateLimitExhaustedError(Exception):
    """Raised when all configured models are rate-limited."""

# ──────────────────────────────────────────────────────────────────────────────
# Load environment before reading API keys.
# ──────────────────────────────────────────────────────────────────────────────
_env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(_env_path)

# ──────────────────────────────────────────────────────────────────────────────
# Groq client — validated at import time so we fail loudly, not silently.
# ──────────────────────────────────────────────────────────────────────────────
_groq_api_key = os.getenv("GROQ_API_KEY")
_openrouter_api_key = os.getenv("OPENROUTER_API_KEY")

groq_client = Groq(api_key=_groq_api_key) if _groq_api_key else None
openrouter_client = (
    OpenAI(api_key=_openrouter_api_key, base_url="https://openrouter.ai/api/v1")
    if _openrouter_api_key
    else None
)

if not groq_client and not openrouter_client:
    raise EnvironmentError(
        "Neither GROQ_API_KEY nor OPENROUTER_API_KEY is set in your .env file. "
        "The LLM brain cannot function without at least one provider."
    )

_model_blocklist = set()

USERNAME = os.getenv("USERNAME") or getpass.getuser()
HOME_DIR = os.path.expanduser("~")
DESKTOP_DIR = os.path.join(HOME_DIR, "Desktop")

SYSTEM_PROMPT = f"""You are ARIA, a highly intelligent and professional AI assistant. 
You are currently providing verbal responses directly to the user's audio speakers.

CRITICAL RULES:
1. KEEP YOUR RESPONSES EXTREMELY SHORT AND CONCISE. (1 to 3 sentences maximum).
2. DO NOT use markdown symbols like asterisks (*) or hashes (#) because the Text-to-Speech audio engine will literally read them out loud. However, you MAY use newlines/line breaks to format lists cleanly on the screen.
3. Be polite, direct, and slightly formal but friendly.
4. If the user asks to search the web or find recent news, ALWAYS call tavily_search and set query to the user's request text. Only ask for a query if the user provided no topic at all.
5. When using tavily_search, ALWAYS pass the 'query' argument as a string containing the search terms. Never call it with empty arguments. Example: tavily_search(query="latest AI news 2026").
6. The 'sequentialthinking' tool is for internal reasoning only and does NOT execute actions. Only call it when you must reason in multiple steps. When calling it, include the required fields: thought, nextThoughtNeeded, thoughtNumber, totalThoughts (and optional fields like isRevision, revisesThought, branchFromThought, branchId, needsMoreThoughts). For actions, call the real action tools directly.

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
existing_memory = memory.get_memory()
if not existing_memory:
    memory.add({"role": "system", "content": SYSTEM_PROMPT})
else:
    first_entry = existing_memory[0]
    if first_entry.get("role") != "system" or first_entry.get("content") != SYSTEM_PROMPT:
        # Keep the system prompt in sync across restarts.
        memory.history[0] = {"role": "system", "content": SYSTEM_PROMPT}
        memory._save()


def _resolve_known_fix(error_type, error_message, location, update_callback=None):
    known_fix = error_memory.find_best_fix(
        error_type=error_type,
        error_message=error_message,
        location=location,
    )
    if not known_fix:
        return None

    resolution = known_fix.get("resolution", "").strip()
    if not resolution:
        return None

    notice = f"Known fix found for {error_type}: {resolution}"
    print(f"  [i] {notice}")
    if update_callback:
        try:
            update_callback(notice)
        except Exception:
            pass

    error_memory.record_error(
        error_type=error_type,
        error_message=error_message,
        location=location,
        attempted_step=f"Applied known fix ({known_fix.get('match_type', 'unknown')})",
        outcome="mitigated",
        resolution=resolution,
    )
    return resolution

# Track temporarily rate-limited models to avoid retrying them repeatedly
_rate_limited_until = {}

def _parse_retry_seconds(err_text: str) -> int:
    """Parse human-readable retry hints like 'try again in 30m51.552s' or 'try again in 30m' or 'try again in 45s'."""
    import re
    now_secs = 0
    m = re.search(r"try again in\s*(\d+)m(\d+(?:\.\d+)?)s", err_text)
    if m:
        mins = int(m.group(1))
        secs = float(m.group(2))
        return int(mins * 60 + secs)
    m = re.search(r"try again in\s*(\d+)m", err_text)
    if m:
        mins = int(m.group(1))
        return int(mins * 60)
    m = re.search(r"try again in\s*(\d+(?:\.\d+)?)s", err_text)
    if m:
        secs = float(m.group(1))
        return int(secs)
    # Fallback: look for 'in Xh' or 'hours'
    m = re.search(r"in\s*(\d+)h", err_text)
    if m:
        hours = int(m.group(1))
        return hours * 3600
    return 60  # default 1 minute cooldown


def _base_model_specs():
    specs = []

    if groq_client:
        specs.extend([
            {"provider": "groq", "model": "llama-3.3-70b-versatile"},
            {"provider": "groq", "model": "meta-llama/llama-4-scout-17b-16e-instruct"},
            {"provider": "groq", "model": "llama-3.1-8b-instant"},
        ])

    if openrouter_client:
        env_models = os.getenv("OPENROUTER_FREE_MODELS", "").strip()
        if env_models:
            model_list = [m.strip() for m in env_models.split(",") if m.strip()]
        else:
            # Default OpenRouter free fallback models.
            model_list = [
                "mistralai/mistral-7b-instruct:free",
                "meta-llama/llama-3.1-8b-instruct:free",
                "qwen/qwen2.5-7b-instruct:free",
            ]

        for model in model_list:
            specs.append({"provider": "openrouter", "model": model})

    return specs


def _build_model_specs():
    specs = _base_model_specs()
    if not _model_blocklist:
        return specs
    return [
        spec
        for spec in specs
        if f"{spec['provider']}:{spec['model']}" not in _model_blocklist
    ]


def _fetch_available_model_ids(label, url, api_key):
    if not api_key:
        return None

    try:
        response = requests.get(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=20,
        )
        if response.status_code != 200:
            logger.warning(f"{label} model list request failed: {response.status_code} {response.text}")
            return None
        payload = response.json()
        data = payload.get("data", []) if isinstance(payload, dict) else []
        model_ids = set()
        for entry in data:
            if isinstance(entry, dict):
                model_id = entry.get("id") or entry.get("name")
                if model_id:
                    model_ids.add(model_id)
            elif isinstance(entry, str):
                model_ids.add(entry)
        return model_ids
    except Exception as exc:
        logger.warning(f"{label} model list request failed: {exc}")
        return None


def _preflight_model_availability():
    base_specs = _base_model_specs()
    if not base_specs:
        return

    groq_ids = _fetch_available_model_ids(
        "Groq",
        "https://api.groq.com/openai/v1/models",
        _groq_api_key,
    )
    openrouter_ids = _fetch_available_model_ids(
        "OpenRouter",
        "https://openrouter.ai/api/v1/models",
        _openrouter_api_key,
    )

    for spec in base_specs:
        provider = spec["provider"]
        model = spec["model"]
        key = f"{provider}:{model}"

        if provider == "groq" and groq_ids is not None:
            if model not in groq_ids:
                _model_blocklist.add(key)
                print(f"  [!] Preflight: Groq model '{model}' not available. Skipping.")
        elif provider == "openrouter" and openrouter_ids is not None:
            if model not in openrouter_ids:
                _model_blocklist.add(key)
                print(f"  [!] Preflight: OpenRouter model '{model}' not available. Skipping.")


_preflight_model_availability()


def safe_chat_completion(messages, tools_list=None, tool_choice_val=None, update_callback=None):
    """A hybrid router that cascades through multiple models if rate limits are hit.

    This version respects short cooldowns for models that return rate-limit hints so
    the next model takes the load immediately instead of repeatedly retrying the
    exhausted model.
    """
    import time

    model_specs = _build_model_specs()
    if not model_specs:
        raise RateLimitExhaustedError("No configured models are available for routing.")

    now = time.time()
    # Filter out temporarily rate-limited models
    available_specs = [
        spec for spec in model_specs
        if _rate_limited_until.get(f"{spec['provider']}:{spec['model']}", 0) <= now
    ]

    if not available_specs:
        # If all models are on cooldown, pick the one with the earliest retry time and report it
        soonest = min(
            (
                (spec, _rate_limited_until.get(f"{spec['provider']}:{spec['model']}", now + 3600))
                for spec in model_specs
            ),
            key=lambda item: item[1],
        )
        retry_in = int(max(0, soonest[1] - now))
        raise RateLimitExhaustedError(
            f"All configured models are temporarily rate-limited. Next retry in {retry_in} seconds."
        )

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

    # Iterate over currently available models (preserving original priority order)
    for spec in available_specs:
        provider = spec["provider"]
        model = spec["model"]
        kwargs["model"] = model
        try:
            if provider == "groq" and groq_client:
                return groq_client.chat.completions.create(**kwargs)
            if provider == "openrouter" and openrouter_client:
                return openrouter_client.chat.completions.create(**kwargs)
            raise RuntimeError(f"Provider '{provider}' is not configured.")
        except Exception as e:
            error_str = str(e).lower()

            # ── Rate limit: record cooldown and swap to next model ───────────────────────────
            if "429" in error_str or "rate limit" in error_str or "tokens per day" in error_str or "tokens per minute" in error_str:
                # Parse any 'try again in' hints to set a smarter cooldown
                cooldown = _parse_retry_seconds(str(e))
                rate_key = f"{provider}:{model}"
                _rate_limited_until[rate_key] = time.time() + max(30, cooldown)

                notice = (
                    f"Model {model} ({provider}) limit hit, trying next model. "
                    f"Cooldown set for {cooldown}s."
                )
                print(f"  [!] {notice}")
                error_memory.record_error(
                    error_type="RateLimit",
                    error_message=str(e),
                    location="safe_chat_completion",
                    attempted_step=notice,
                    outcome="transient",
                    context=f"provider={provider},model={model}",
                )
                if update_callback:
                    try:
                        update_callback(notice)
                    except Exception:
                        pass
                logger.warning(f"Rate limit on model '{model}' ({provider}). Trying next. Error: {e}")
                continue

            # ── Decommissioned model: skip to next model ───────────────────────
            if "decommissioned" in error_str or "model_decommissioned" in error_str:
                print(f"  [!] Model '{model}' ({provider}) has been decommissioned. Skipping...")
                logger.warning(f"Model '{model}' ({provider}) decommissioned. Skipping. Error: {e}")
                continue

            if (
                "model not found" in error_str
                or "does not exist" in error_str
                or "invalid model" in error_str
                or "no endpoints found" in error_str
            ):
                print(f"  [!] Model '{model}' ({provider}) not found. Skipping...")
                logger.warning(f"Model '{model}' ({provider}) not found. Error: {e}")
                continue

            # ── Tool call rejected: skip to next model WITH tools still on ──────
            # IMPORTANT: do NOT fall back to text-only here — that causes ARIA to
            # hallucinate the action ("Spotify is opening!") without actually doing it.
            if tools_list and ("tool_use_failed" in error_str or "failed_generation" in error_str):
                print(f"  [!] Model '{model}' ({provider}) rejected a tool call. Trying next model...")
                logger.warning(f"Tool call rejected by '{model}' ({provider}). Skipping to next model. Error: {e}")
                continue  # Try the next model in the list with tools still active

            # ── Auth error: no point trying other models ──────────────────
            if "401" in error_str or "authentication" in error_str or "invalid api key" in error_str:
                logger.error(f"API key is invalid or expired for provider '{provider}': {e}")
                raise ConnectionError(
                    f"Your {provider.upper()} API key is invalid or expired. "
                    "Please update it in your .env file."
                ) from e

            # ── Network error: no point trying other models ───────────────
            if "connection" in error_str or "timeout" in error_str or "network" in error_str:
                logger.error(f"Network error contacting provider '{provider}' API: {e}")
                raise ConnectionError(
                    f"Could not reach the {provider} API. Please check your internet connection."
                ) from e

            # ── Anything else: surface it immediately ─────────────────────
            logger.error(
                f"Provider API error on model '{model}' ({provider}): {e}\n{traceback.format_exc()}"
            )
            raise e

    # All available models tried and failed (either due to tool rejections or other errors)
    raise RateLimitExhaustedError("All limits are hit. Working will be done after 24 hours.")

def ask_aria(user_input, update_callback=None):
    global memory
    
    # Append the user's message
    memory.add({"role": "user", "content": user_input})
    
    try:
        # 1. Ask the AI if it wants to use a tool or just reply directly
        response = safe_chat_completion(
            messages=memory.get_memory(),
            tools_list=tools,
            tool_choice_val="auto",
            update_callback=update_callback,
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
                    error_memory.record_error(
                        error_type="ToolArgumentError",
                        error_message=str(e),
                        location=f"tool:{function_name}",
                        attempted_step=f"Called with args: {function_args}",
                        outcome="open",
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
                    error_memory.record_error(
                        error_type=type(e).__name__,
                        error_message=str(e),
                        location=f"tool:{function_name}",
                        attempted_step=f"Executed with args: {function_args}",
                        outcome="open",
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

            final_response = safe_chat_completion(
                messages=synthesis_messages,
                update_callback=update_callback,
            )
            
            final_text = final_response.choices[0].message.content or ""
            # Strip hallucinated XML tags that reasoning/fallback models inject.
            # 1. <think>...</think> or <thinking>...</thinking>
            final_text = re.sub(r'<think(?:ing)?>.*?</think(?:ing)?>', '', final_text, flags=re.DOTALL)
            # 2. <function=...></function> (Groq tool hallucinations)
            final_text = re.sub(r'<function=.*?</function>', '', final_text, flags=re.DOTALL)
            final_text = final_text.strip()

            if not final_text and executed_tool_outputs:
                # Some fallback models occasionally return an empty message after tools.
                # Build a concise deterministic response from the latest tool outputs.
                summarized_outputs = []
                for output in executed_tool_outputs:
                    name = output.get("name", "tool")
                    content = str(output.get("content", "")).strip().replace("\n", " ")
                    if len(content) > 180:
                        content = content[:180].rstrip() + "..."
                    summarized_outputs.append(f"{name}: {content}")
                final_text = "Here is what I found. " + " ".join(summarized_outputs)
            
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
            
    except RateLimitExhaustedError as e:
        known_fix_resolution = _resolve_known_fix(
            error_type="RateLimitExhausted",
            error_message=str(e),
            location="ask_aria",
            update_callback=update_callback,
        )
        if known_fix_resolution:
            return known_fix_resolution

        logger.warning(f"Brain (LLM) Rate Limit Exhausted: {e}")
        print(f"[-] Brain (LLM) Rate Limit Exhausted: {e}")
        error_memory.record_error(
            error_type="RateLimitExhausted",
            error_message=str(e),
            location="ask_aria",
            attempted_step="Exhausted all configured models",
            outcome="mitigated",
            resolution="All limits are hit. Working will be done after 24 hours.",
        )
        return str(e)

    except ConnectionError as e:
        known_fix_resolution = _resolve_known_fix(
            error_type="ConnectionError",
            error_message=str(e),
            location="ask_aria",
            update_callback=update_callback,
        )
        if known_fix_resolution:
            return known_fix_resolution

        # Network or auth errors — specific, actionable message
        logger.error(f"Brain (LLM) Connection Error: {e}")
        print(f"[-] Brain (LLM) Connection Error: {e}")
        error_memory.record_error(
            error_type="ConnectionError",
            error_message=str(e),
            location="ask_aria",
            attempted_step="Called safe_chat_completion",
            outcome="open",
        )
        return "I'm unable to reach my cloud reasoning engine right now, sir. Please check your internet connection and API keys."

    except MemoryError:
        known_fix_resolution = _resolve_known_fix(
            error_type="MemoryError",
            error_message="Conversation history too large",
            location="ask_aria",
            update_callback=update_callback,
        )

        # Conversation history is too large — clear it and recover
        logger.error("Brain (LLM) MemoryError: Conversation history too large. Resetting.")
        print("[-] Brain (LLM) Memory Overflow: Conversation history was too large. Resetting memory.")
        error_memory.record_error(
            error_type="MemoryError",
            error_message="Conversation history too large",
            location="ask_aria",
            attempted_step="Cleared memory and re-added system prompt",
            outcome="mitigated",
            resolution="Conversation memory reset to recover from overflow",
        )
        memory.clear()
        memory.add({"role": "system", "content": SYSTEM_PROMPT})
        if known_fix_resolution:
            return known_fix_resolution
        return "My conversation memory has been reset due to overflow, sir. Please repeat your request."

    except Exception as e:
        known_fix_resolution = _resolve_known_fix(
            error_type=type(e).__name__,
            error_message=str(e),
            location="ask_aria",
            update_callback=update_callback,
        )
        if known_fix_resolution:
            return known_fix_resolution

        logger.error(f"Brain (LLM) unhandled error: {e}\n{traceback.format_exc()}")
        print(f"[-] Brain (LLM) Error: {type(e).__name__}: {e}")
        error_memory.record_error(
            error_type=type(e).__name__,
            error_message=str(e),
            location="ask_aria",
            attempted_step="General exception handler",
            outcome="open",
        )
        return "I'm sorry, sir. I encountered an internal error. Please try your request again."
