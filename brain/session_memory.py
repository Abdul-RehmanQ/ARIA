import os
import json

MEMORY_DIR = os.path.join(os.path.dirname(__file__), "..", "memory")
DEFAULT_PATH = os.path.join(MEMORY_DIR, "aria_memory.json")

MAX_MESSAGES = 60        # trigger compression above this
KEEP_RECENT = 20         # always preserve this many recent messages
MIN_OLD_TO_COMPRESS = 10 # only compress if there is enough old content


class SessionMemory:
    def __init__(self, session_id="aria_main", db_path=DEFAULT_PATH):
        self.db_path = db_path
        self.history = []
        self._load()

    def _clean_message(self, message: dict) -> dict:
        """Sanitize message to contain only standard API fields, preventing BadRequest errors from providers like Groq."""
        if not isinstance(message, dict):
            return message

        cleaned = {"role": message.get("role")}
        
        # Include content if present
        if "content" in message and message["content"] is not None:
            cleaned["content"] = message["content"]
            
        # Include name (for tool responses)
        if "name" in message:
            cleaned["name"] = message["name"]
            
        # Include tool_call_id (for tool responses)
        if "tool_call_id" in message:
            cleaned["tool_call_id"] = message["tool_call_id"]
            
        # Include tool_calls (for assistant tool calls)
        if "tool_calls" in message and message["tool_calls"] is not None:
            cleaned_tool_calls = []
            for tc in message["tool_calls"]:
                cleaned_tc = {
                    "id": tc.get("id"),
                    "type": tc.get("type", "function"),
                    "function": {
                        "name": tc["function"].get("name") if isinstance(tc.get("function"), dict) else None,
                        "arguments": tc["function"].get("arguments") if isinstance(tc.get("function"), dict) else None
                    }
                }
                cleaned_tool_calls.append(cleaned_tc)
            cleaned["tool_calls"] = cleaned_tool_calls
        return cleaned

    def _load(self):
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, "r", encoding="utf-8") as f:
                    raw_history = json.load(f)
                
                # Sanitize history to prevent API errors from extra fields
                self.history = [self._clean_message(msg) for msg in raw_history]
            except Exception:
                pass

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            with open(self.db_path, "w", encoding="utf-8") as f:
                json.dump(self.history, f, indent=2)
        except Exception:
            pass

    def add(self, message):
        self.history.append(self._clean_message(message))
        self._save()

    def get_memory(self):
        return self.history

    def clear(self):
        self.history.clear()
        self._save()

    def needs_compression(self) -> bool:
        return len(self.history) > MAX_MESSAGES

    def compress(self, summarizer_fn) -> bool:
        """
        Compresses old messages into a summary.
        summarizer_fn: callable that takes a list of messages and returns a summary string.
        Returns True if compression was performed.
        """
        history = self.history
        # Always keep index 0 (system prompt) and last KEEP_RECENT messages
        if len(history) < 2 + MIN_OLD_TO_COMPRESS:
            return False

        system_prompt = history[0]
        old_messages = history[1:-KEEP_RECENT]
        recent_messages = history[-KEEP_RECENT:]

        if len(old_messages) < MIN_OLD_TO_COMPRESS:
            return False

        try:
            summary_text = summarizer_fn(old_messages)
        except Exception as e:
            print(f"  [!] Memory compression failed: {e}")
            return False

        summary_block = {
            "role": "system",
            "content": f"[Compressed memory — summary of earlier conversation]\n{summary_text}"
        }

        self.history = [system_prompt, summary_block] + recent_messages
        self._save()
        print(f"  [i] Memory compressed: {len(old_messages)} messages → 1 summary block. "
              f"Kept {len(recent_messages)} recent messages.")
        return True
