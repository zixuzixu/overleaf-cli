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
    # Overleaf internal
    ".overleaf/",
]


def load_patterns(project_dir: Path) -> list[str]:
    """Load ignore patterns from .overleafignore, merged with defaults."""
    patterns = list(DEFAULT_PATTERNS)
    ignore_file = project_dir / IGNORE_FILE
    if ignore_file.exists():
        for line in ignore_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                patterns.append(line)
    return patterns


def is_ignored(rel_path: str, patterns: list[str]) -> bool:
    """Check if a relative path matches any ignore pattern."""
    parts = Path(rel_path).parts
    for pattern in patterns:
        # Directory pattern (ends with /)
        if pattern.endswith("/"):
            dir_name = pattern.rstrip("/")
            if any(p == dir_name for p in parts[:-1]) or (parts and parts[0] == dir_name):
                return True
            continue
        # File pattern — match against filename or full path
        filename = Path(rel_path).name
        if fnmatch.fnmatch(filename, pattern):
            return True
        if fnmatch.fnmatch(rel_path, pattern):
            return True
    return False
