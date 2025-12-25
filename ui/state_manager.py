import json
import os
from typing import Any, Dict

STATE_FILENAME = ".dice_tool_state.json"

def default_state_path() -> str:
    """Return path to the JSON state file in the user's home directory."""
    home = os.path.expanduser("~")
    return os.path.join(home, STATE_FILENAME)

def save_state(state: Dict[str, Any], path: str = None) -> None:
    """Save state dict to JSON file (best-effort, atomic-ish write)."""
    if path is None:
        path = default_state_path()
    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        os.replace(tmp, path)
    except Exception:
        # Best-effort: don't crash the program on save failures
        pass

def load_state(path: str = None) -> Dict[str, Any]:
    """Load and return state dict from JSON file. Returns empty dict on error."""
    if path is None:
        path = default_state_path()
    try:
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}
