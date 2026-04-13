"""Tests for manifest module."""

import json
from pathlib import Path

from overleaf_cli.manifest import Manifest, hash_file, hash_content


def test_hash_content_str():
    h = hash_content("hello")
    assert isinstance(h, str)
    assert len(h) == 64  # SHA-256 hex digest


def test_hash_content_bytes():
    h1 = hash_content("hello")
    h2 = hash_content(b"hello")
    assert h1 == h2


def test_hash_file(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("hello world")
    h = hash_file(f)
    assert h == hash_content("hello world")


def test_manifest_init_and_save(tmp_path):
    m = Manifest(tmp_path)
    assert m.project_id == ""

    m.init("proj123", "My Project", "https://www.overleaf.com")
    m.save()

    assert (tmp_path / ".overleaf" / "manifest.json").exists()
    data = json.loads((tmp_path / ".overleaf" / "manifest.json").read_text())
    assert data["project_id"] == "proj123"
    assert data["project_name"] == "My Project"
    assert data["last_sync"] != ""


def test_manifest_set_and_get_file(tmp_path):
    m = Manifest(tmp_path)
    m.init("p1", "Test", "https://www.overleaf.com")

    m.set_file("main.tex", "doc_id_1", "doc", "abc123")
    entry = m.get_file("main.tex")
    assert entry is not None
    assert entry["id"] == "doc_id_1"
    assert entry["type"] == "doc"
    assert entry["hash"] == "abc123"


def test_manifest_remove_file(tmp_path):
    m = Manifest(tmp_path)
    m.set_file("main.tex", "id1", "doc", "hash1")
    assert m.get_file("main.tex") is not None

    m.remove_file("main.tex")
    assert m.get_file("main.tex") is None


def test_manifest_remove_nonexistent(tmp_path):
    m = Manifest(tmp_path)
    m.remove_file("nope.tex")  # should not raise


def test_manifest_all_files(tmp_path):
    m = Manifest(tmp_path)
    m.set_file("a.tex", "1", "doc", "h1")
    m.set_file("b.png", "2", "file", "h2")
    assert len(m.all_files()) == 2


def test_manifest_reload(tmp_path):
    m = Manifest(tmp_path)
    m.init("p1", "Test", "https://www.overleaf.com")
    m.set_file("main.tex", "id1", "doc", "hash1")
    m.save()

    m2 = Manifest(tmp_path)
    assert m2.project_id == "p1"
    assert m2.get_file("main.tex")["hash"] == "hash1"


def test_get_local_changes_added(tmp_path):
    m = Manifest(tmp_path)
    m.init("p1", "Test", "https://www.overleaf.com")
    m.save()

    (tmp_path / "new_file.tex").write_text("new content")

    added, modified, deleted = m.get_local_changes()
    assert "new_file.tex" in added
    assert modified == []
    assert deleted == []


def test_get_local_changes_modified(tmp_path):
    m = Manifest(tmp_path)
    m.init("p1", "Test", "https://www.overleaf.com")

    (tmp_path / "main.tex").write_text("original")
    m.set_file("main.tex", "id1", "doc", hash_content("original"))
    m.save()

    (tmp_path / "main.tex").write_text("changed")

    added, modified, deleted = m.get_local_changes()
    assert added == []
    assert "main.tex" in modified
    assert deleted == []


def test_get_local_changes_deleted(tmp_path):
    m = Manifest(tmp_path)
    m.init("p1", "Test", "https://www.overleaf.com")
    m.set_file("gone.tex", "id1", "doc", "somehash")
    m.save()

    added, modified, deleted = m.get_local_changes()
    assert added == []
    assert modified == []
    assert "gone.tex" in deleted


def test_get_local_changes_ignores_manifest_dir(tmp_path):
    m = Manifest(tmp_path)
    m.init("p1", "Test", "https://www.overleaf.com")
    m.save()  # creates .overleaf/manifest.json

    added, modified, deleted = m.get_local_changes()
    assert added == []  # .overleaf/ files should be ignored
