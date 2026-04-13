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


def load_git_auth() -> dict | None:
    """Load git credentials (email + token) for Overleaf git bridge."""
    session = load_session()
    if not session:
        return None
    email = session.get("git_email")
    token = session.get("git_token")
    if email and token:
        return {"email": email, "token": token}
    return None


def save_git_auth(email: str, token: str):
    """Save git credentials alongside the session."""
    session = load_session()
    if not session:
        raise RuntimeError("No session found. Run 'overleaf login' first.")
    session["git_email"] = email
    session["git_token"] = token
    ensure_config_dir()
    SESSION_FILE.write_text(json.dumps(session, indent=2))
