"""Tests for config module."""

import json
from pathlib import Path

from overleaf_cli import config


def test_save_and_load_session(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(config, "SESSION_FILE", tmp_path / "session.json")

    assert config.load_session() is None

    config.save_session("test_cookie_value", "https://overleaf.example.com")

    session = config.load_session()
    assert session is not None
    assert session["cookie"] == "test_cookie_value"
    assert session["base_url"] == "https://overleaf.example.com"


def test_save_session_default_url(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(config, "SESSION_FILE", tmp_path / "session.json")

    config.save_session("abc")
    session = config.load_session()
    assert session["base_url"] == "https://www.overleaf.com"


def test_clear_session(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(config, "SESSION_FILE", tmp_path / "session.json")

    config.save_session("cookie")
    assert config.load_session() is not None

    config.clear_session()
    assert config.load_session() is None


def test_clear_session_no_file(tmp_path, monkeypatch):
    """clear_session should not raise if no session file exists."""
    monkeypatch.setattr(config, "SESSION_FILE", tmp_path / "nonexistent.json")
    config.clear_session()  # should not raise


def test_load_session_corrupt_json(tmp_path, monkeypatch):
    session_file = tmp_path / "session.json"
    session_file.write_text("not valid json{{{")
    monkeypatch.setattr(config, "SESSION_FILE", session_file)

    assert config.load_session() is None


def test_ensure_config_dir(tmp_path, monkeypatch):
    new_dir = tmp_path / "sub" / "dir"
    monkeypatch.setattr(config, "CONFIG_DIR", new_dir)
    config.ensure_config_dir()
    assert new_dir.is_dir()
