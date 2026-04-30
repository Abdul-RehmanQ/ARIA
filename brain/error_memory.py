import os
import json
import hashlib
from datetime import datetime


class ErrorMemory:
    """Stores recurring error patterns and attempted fixes for faster recovery."""

    def __init__(self, db_path=os.path.join("memory", "error_memory.json")):
        self.db_path = db_path
        self.entries = {}
        self._load()

    def _load(self):
        if not os.path.exists(self.db_path):
            self.entries = {}
            return

        try:
            with open(self.db_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    self.entries = data
                else:
                    self.entries = {}
        except Exception:
            self.entries = {}

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            with open(self.db_path, "w", encoding="utf-8") as f:
                json.dump(self.entries, f, indent=2)
        except Exception:
            # Error memory must never crash core assistant flow.
            pass

    def _signature(self, error_type, error_message, location=""):
        base = f"{error_type}|{error_message}|{location}".strip().lower()
        return hashlib.sha256(base.encode("utf-8")).hexdigest()[:16]

    def record_error(
        self,
        error_type,
        error_message,
        location="",
        attempted_step=None,
        outcome="open",
        resolution=None,
        context=None,
    ):
        now = datetime.utcnow().isoformat() + "Z"
        signature = self._signature(error_type, error_message, location)

        if signature not in self.entries:
            self.entries[signature] = {
                "signature": signature,
                "error_type": str(error_type),
                "error_message": str(error_message),
                "location": str(location),
                "first_seen": now,
                "last_seen": now,
                "count": 1,
                "outcome": str(outcome),
                "resolution": resolution or "",
                "attempted_steps": [],
                "contexts": [],
            }
        else:
            self.entries[signature]["count"] += 1
            self.entries[signature]["last_seen"] = now
            self.entries[signature]["outcome"] = str(outcome)
            if resolution:
                self.entries[signature]["resolution"] = resolution

        if attempted_step:
            self.entries[signature]["attempted_steps"].append({
                "at": now,
                "step": str(attempted_step),
            })
            self.entries[signature]["attempted_steps"] = self.entries[signature]["attempted_steps"][-25:]

        if context:
            self.entries[signature]["contexts"].append({
                "at": now,
                "context": str(context),
            })
            self.entries[signature]["contexts"] = self.entries[signature]["contexts"][-25:]

        self._save()
        return signature

    def get_known_fix(self, error_type, error_message, location=""):
        signature = self._signature(error_type, error_message, location)
        entry = self.entries.get(signature)
        if not entry:
            return None

        if entry.get("outcome") in {"resolved", "mitigated"} and entry.get("resolution"):
            return {
                "signature": signature,
                "resolution": entry.get("resolution"),
                "attempted_steps": entry.get("attempted_steps", []),
                "count": entry.get("count", 1),
            }
        return None

    def find_best_fix(self, error_type, error_message="", location=""):
        """Finds the most relevant known fix using exact and fallback matching."""
        exact = self.get_known_fix(error_type, error_message, location)
        if exact:
            exact["match_type"] = "exact"
            return exact

        candidates = []
        for entry in self.entries.values():
            if entry.get("outcome") not in {"resolved", "mitigated"}:
                continue
            if not entry.get("resolution"):
                continue
            if str(entry.get("error_type", "")).lower() != str(error_type).lower():
                continue

            score = 0
            if location and str(entry.get("location", "")).lower() == str(location).lower():
                score += 3
            if error_message:
                lhs = str(entry.get("error_message", "")).lower()
                rhs = str(error_message).lower()
                if lhs == rhs:
                    score += 3
                elif rhs in lhs or lhs in rhs:
                    score += 1

            score += min(int(entry.get("count", 1)), 5)
            candidates.append((score, entry))

        if not candidates:
            return None

        candidates.sort(key=lambda item: (item[0], item[1].get("last_seen", "")), reverse=True)
        best = candidates[0][1]
        return {
            "signature": best.get("signature"),
            "resolution": best.get("resolution"),
            "attempted_steps": best.get("attempted_steps", []),
            "count": best.get("count", 1),
            "match_type": "fallback",
        }


error_memory = ErrorMemory()
