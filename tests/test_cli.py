"""Tests for CLI commands (no network required)."""

from click.testing import CliRunner

from overleaf_cli import config
from overleaf_cli.cli import main


def test_help():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "Overleaf CLI" in result.output


def test_all_commands_registered():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    for cmd in ["login", "logout", "projects", "clone", "pull", "push", "status"]:
        assert cmd in result.output


def test_logout(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(config, "SESSION_FILE", tmp_path / "session.json")
    config.save_session("test_cookie")

    runner = CliRunner()
    result = runner.invoke(main, ["logout"])
    assert result.exit_code == 0
    assert "Logged out" in result.output
    assert config.load_session() is None


def test_clone_help():
    runner = CliRunner()
    result = runner.invoke(main, ["clone", "--help"])
    assert result.exit_code == 0
    assert "PROJECT_ID" in result.output
    assert "--name" in result.output


def test_pull_no_manifest():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["pull"])
        assert result.exit_code != 0
        assert "Not in an Overleaf project" in result.output


def test_push_no_manifest():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["push"])
        assert result.exit_code != 0
        assert "Not in an Overleaf project" in result.output


def test_status_no_manifest():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["status"])
        assert result.exit_code != 0
        assert "Not in an Overleaf project" in result.output
