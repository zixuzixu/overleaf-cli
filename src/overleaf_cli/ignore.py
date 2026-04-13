"""Ignore patterns for overleaf-cli, similar to .gitignore."""

import fnmatch
from pathlib import Path

IGNORE_FILE = ".overleafignore"

# LaTeX compile outputs and intermediate files
DEFAULT_PATTERNS = [
    # PDF output
    "*.pdf",
    # LaTeX intermediate files
    "*.aux",
    "*.log",
    "*.out",
    "*.toc",
    "*.lof",
    "*.lot",
    "*.loa",
    "*.fls",
    "*.fdb_latexmk",
    "*.synctex.gz",
    "*.synctex",
    "*.blg",
    "*.bbl",
    "*.bcf",
    "*.run.xml",
    "*.nav",
    "*.snm",
    "*.vrb",
    "*.nlo",
    "*.nls",
    "*.ilg",
    "*.ind",
    "*.idx",
    "*.glo",
    "*.gls",
    "*.glg",
    "*.ist",
    "*.acn",
    "*.acr",
    "*.alg",
    "*.xdv",
    "*.dvi",
    "*.ps",
    "*-blx.bib",
    "*.@bstract",
    # minitoc intermediate files
    "*.maf",
    "*.mtc",
    "*.mtc0",
    "*.mtc1",
    "*.mtc2",
    "*.mtc3",
    "*.mlf",
    "*.mlt",
    # Archive / compressed files
    "*.tar.gz",
    "*.tar",
    "*.zip",
    "*.rar",
    "*.7z",
    # Overleaf internal metadata
    "00README.json",
    # Common non-LaTeX files
    "*.pyc",
    "*.DS_Store",
    ".git/",
    ".gitignore",
    "__pycache__/",
    # Overleaf internal
    ".overleaf/",
]


def load_patterns(project_dir: Path) -> tuple[list[str], list[str]]:
    """Load ignore and negation patterns from .overleafignore, merged with defaults.

    Returns (ignore_patterns, negation_patterns). Lines starting with '!' are
    negation patterns that override ignore rules (like .gitignore).
    """
    ignore = list(DEFAULT_PATTERNS)
    negate = []
    ignore_file = project_dir / IGNORE_FILE
    if ignore_file.exists():
        for line in ignore_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("!"):
                negate.append(line[1:])  # strip the '!'
            else:
                ignore.append(line)
    return ignore, negate


def is_ignored(rel_path: str, patterns: list[str] | tuple[list[str], list[str]]) -> bool:
    """Check if a relative path matches any ignore pattern.

    Accepts either a flat list (legacy) or a (ignore, negate) tuple.
    Negation patterns (from lines starting with '!') un-ignore matched files.
    """
    # Support both old (flat list) and new (tuple) signatures
    if isinstance(patterns, tuple):
        ignore_patterns, negate_patterns = patterns
    else:
        ignore_patterns, negate_patterns = patterns, []

    parts = Path(rel_path).parts
    filename = Path(rel_path).name

    # Check negation first — if a file matches a negation pattern, it is NOT ignored
    for pattern in negate_patterns:
        if pattern.endswith("/"):
            dir_name = pattern.rstrip("/")
            if any(p == dir_name for p in parts[:-1]) or (parts and parts[0] == dir_name):
                return False
        else:
            if fnmatch.fnmatch(filename, pattern):
                return False
            if fnmatch.fnmatch(rel_path, pattern):
                return False

    # Check ignore patterns
    for pattern in ignore_patterns:
        if pattern.endswith("/"):
            dir_name = pattern.rstrip("/")
            if any(p == dir_name for p in parts[:-1]) or (parts and parts[0] == dir_name):
                return True
            continue
        if fnmatch.fnmatch(filename, pattern):
            return True
        if fnmatch.fnmatch(rel_path, pattern):
            return True
    return False
