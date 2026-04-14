"""Tests for ignore module."""

from pathlib import Path

from overleaf_cli.ignore import is_ignored, load_patterns, DEFAULT_PATTERNS


def test_default_patterns_ignore_pdf():
    assert is_ignored("main.pdf", DEFAULT_PATTERNS)
    assert is_ignored("output/thesis.pdf", DEFAULT_PATTERNS)


def test_default_patterns_ignore_aux():
    assert is_ignored("main.aux", DEFAULT_PATTERNS)
    assert is_ignored("chapter1.log", DEFAULT_PATTERNS)
    assert is_ignored("main.toc", DEFAULT_PATTERNS)
    assert is_ignored("main.fdb_latexmk", DEFAULT_PATTERNS)
    assert is_ignored("main.synctex.gz", DEFAULT_PATTERNS)
    assert is_ignored("main.blg", DEFAULT_PATTERNS)
    assert is_ignored("main.bbl", DEFAULT_PATTERNS)
    assert is_ignored("main.out", DEFAULT_PATTERNS)
    assert is_ignored("main.lof", DEFAULT_PATTERNS)
    assert is_ignored("main.lot", DEFAULT_PATTERNS)
    assert is_ignored("main.nav", DEFAULT_PATTERNS)
    assert is_ignored("main.snm", DEFAULT_PATTERNS)
    assert is_ignored("main.@bstract", DEFAULT_PATTERNS)


def test_default_patterns_ignore_minitoc():
    assert is_ignored("main.maf", DEFAULT_PATTERNS)
    assert is_ignored("main.mtc", DEFAULT_PATTERNS)
    assert is_ignored("main.mtc0", DEFAULT_PATTERNS)
    assert is_ignored("main.mtc1", DEFAULT_PATTERNS)


def test_default_patterns_ignore_archives():
    assert is_ignored("source.tar.gz", DEFAULT_PATTERNS)
    assert is_ignored("backup.zip", DEFAULT_PATTERNS)
    assert is_ignored("data.tar", DEFAULT_PATTERNS)
    assert is_ignored("old.rar", DEFAULT_PATTERNS)


def test_default_patterns_ignore_overleaf_metadata():
    assert is_ignored("00README.json", DEFAULT_PATTERNS)


def test_default_patterns_allow_tex():
    assert not is_ignored("main.tex", DEFAULT_PATTERNS)
    assert not is_ignored("chapters/intro.tex", DEFAULT_PATTERNS)


def test_default_patterns_allow_bib():
    assert not is_ignored("references.bib", DEFAULT_PATTERNS)


def test_default_patterns_allow_images():
    assert not is_ignored("figures/fig1.png", DEFAULT_PATTERNS)
    assert not is_ignored("images/photo.jpg", DEFAULT_PATTERNS)
    assert not is_ignored("diagram.eps", DEFAULT_PATTERNS)


def test_default_patterns_allow_cls_sty():
    assert not is_ignored("custom.cls", DEFAULT_PATTERNS)
    assert not is_ignored("mystyle.sty", DEFAULT_PATTERNS)


def test_directory_pattern():
    patterns = [".overleaf/"]
    assert is_ignored(".overleaf/manifest.json", patterns)
    assert not is_ignored("overleaf_notes.txt", patterns)


def test_custom_patterns_from_file(tmp_path):
    ignore_file = tmp_path / ".overleafignore"
    ignore_file.write_text("# Custom ignores\n*.backup\nold_stuff/\n")

    patterns = load_patterns(tmp_path)
    assert is_ignored("main.backup", patterns)
    assert is_ignored("old_stuff/file.tex", patterns)
    # defaults still work
    assert is_ignored("main.pdf", patterns)
    assert not is_ignored("main.tex", patterns)


def test_load_patterns_no_file(tmp_path):
    ignore, negate = load_patterns(tmp_path)
    assert ignore == DEFAULT_PATTERNS
    assert negate == []


def test_negation_unignores_matching_files():
    """Negation (!) un-ignores files that match a default ignore rule."""
    patterns = (["*.pdf"], ["figures/*.pdf"])
    assert is_ignored("main.pdf", patterns)
    assert not is_ignored("figures/diagram.pdf", patterns)
    assert is_ignored("output/thesis.pdf", patterns)


def test_negation_with_filename_pattern():
    """Negation with a bare filename pattern."""
    patterns = (["*.log"], ["important.log"])
    assert is_ignored("build.log", patterns)
    assert not is_ignored("important.log", patterns)


def test_negation_with_directory_pattern():
    """Negation with a directory pattern un-ignores files in that directory."""
    patterns = (["drafts/"], ["drafts/"])
    assert not is_ignored("drafts/paper.tex", patterns)


def test_load_patterns_with_negation(tmp_path):
    ignore_file = tmp_path / ".overleafignore"
    ignore_file.write_text("*.backup\n!important.backup\nold_stuff/\n")

    ignore, negate = load_patterns(tmp_path)
    assert "*.backup" in ignore
    assert "old_stuff/" in ignore
    assert "important.backup" in negate
    # defaults still present
    assert "*.pdf" in ignore


def test_nested_path_matching():
    patterns = ["*.log"]
    assert is_ignored("build/output.log", patterns)
    assert is_ignored("deep/nested/dir/file.log", patterns)


def test_full_path_pattern():
    patterns = ["build/*.o"]
    assert is_ignored("build/main.o", patterns)
    assert not is_ignored("src/main.o", patterns)
