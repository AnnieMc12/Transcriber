"""Persistent configuration management.

Stores settings in the user's AppData directory on Windows,
or ~/.config/voxtral-transcriber on other platforms.
"""

import json
import os
import sys
from pathlib import Path

APP_NAME = "VoxtralTranscriber"
CONFIG_FILENAME = "config.json"


def _get_config_dir() -> Path:
    """Return the platform-appropriate config directory."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA")
        if base:
            return Path(base) / APP_NAME
    # Fallback for non-Windows or missing APPDATA
    return Path.home() / ".config" / APP_NAME.lower()


def _get_config_path() -> Path:
    config_dir = _get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / CONFIG_FILENAME


def load_config() -> dict:
    """Load config from disk. Returns empty dict if no config exists."""
    path = _get_config_path()
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_config(config: dict):
    """Save config dict to disk."""
    path = _get_config_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def get_api_key() -> str:
    """Return the stored API key, or empty string if not set."""
    return load_config().get("api_key", "")


def set_api_key(key: str):
    """Persist the API key."""
    config = load_config()
    config["api_key"] = key
    save_config(config)
