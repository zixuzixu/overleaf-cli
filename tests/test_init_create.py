"""Tests for init and create CLI commands."""

from click.testing import CliRunner

from overleaf_cli.cli import main
from overleaf_cli.manifest import Manifest


def test_init_help():
    runner = CliRunner()
    result = runner.invoke(main, ["init", "--help"])
    assert result.exit_code == 0
    assert "PROJECT_ID" in result.output
    assert "Link current directory" in result.output


def test_create_help():
    runner = CliRunner()
    result = runner.invoke(main, ["create", "--help"])
    assert result.exit_code == 0
    assert "NAME" in result.output
    assert "Create a new Overleaf project" in result.output


def test_commands_registered():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert "init" in result.output
    assert "create" in result.output


def test_init_already_linked(tmp_path):
    """init should fail if .overleaf/manifest.json already exists with a project_id."""
    m = Manifest(tmp_path)
    m.init("existing_id", "Existing", "https://www.overleaf.com")
    m.save()

    from overleaf_cli.sync import init_project
    import click
    import pytest

    with pytest.raises(click.ClickException, match="Already linked"):
        init_project("new_id", "New", "https://www.overleaf.com", tmp_path)


def test_init_creates_manifest(tmp_path):
    """init should create manifest with local files tracked."""
    (tmp_path / "main.tex").write_text("\\documentclass{article}")
    (tmp_path / "refs.bib").write_text("@article{test}")

    from overleaf_cli.sync import init_project
    init_project("proj123", "Test Project", "https://www.overleaf.com", tmp_path)

    m = Manifest(tmp_path)
    assert m.project_id == "proj123"
    assert m.get_file("main.tex") is not None
    assert m.get_file("refs.bib") is not None


def test_init_respects_ignore(tmp_path):
    """init should skip ignored files."""
    (tmp_path / "main.tex").write_text("\\documentclass{article}")
    (tmp_path / "main.pdf").write_bytes(b"fake pdf")
    (tmp_path / "main.aux").write_text("aux content")

    from overleaf_cli.sync import init_project
    init_project("proj123", "Test", "https://www.overleaf.com", tmp_path)

    m = Manifest(tmp_path)
    assert m.get_file("main.tex") is not None
    assert m.get_file("main.pdf") is None  # ignored by default
    assert m.get_file("main.aux") is None  # ignored by default
