"""Configuration management for overleaf-cli."""

import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "overleaf-cli"
SESSION_FILE = CONFIG_DIR / "session.json"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_BASE_URL = "https://www.overleaf.com"


def ensure_config_dir():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_session() -> dict | None:
    """Load saved session (cookie + base_url)."""
    if not SESSION_FILE.exists():
        return None
    try:
        return json.loads(SESSION_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def save_session(cookie_value: str, base_url: str = DEFAULT_BASE_URL):
    """Persist session cookie to disk."""
    ensure_config_dir()
    SESSION_FILE.write_text(json.dumps({
        "cookie": cookie_value,
        "base_url": base_url,
    }, indent=2))


def clear_session():
    """Remove saved session."""
    if SESSION_FILE.exists():
        SESSION_FILE.unlink()
