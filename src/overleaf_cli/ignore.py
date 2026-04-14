"""Ignore patterns for overleaf-cli, similar to .gitignore.

Strategy: whitelist-first. We only upload files that LaTeX actually needs
to compile. Everything else is ignored unless explicitly un-ignored via
.overleafignore negation patterns.
"""

import fnmatch
import re
from pathlib import Path

IGNORE_FILE = ".overleafignore"

# Extensions that are essential LaTeX source/resource files
_ESSENTIAL_EXTS = frozenset((
    # LaTeX source
    ".tex", ".bib", ".bst", ".cls", ".sty", ".dtx", ".ins", ".ltx",
    ".def", ".cfg", ".fd",
    # Figures (common image formats)
    ".pdf", ".png", ".jpg", ".jpeg", ".eps", ".svg", ".tikz",
    # Data / tables
    ".csv", ".dat",
    # Font files
    ".ttf", ".otf", ".woff", ".woff2", ".pfb", ".afm", ".tfm", ".vf",
    ".enc", ".map",
))

# Files always ignored regardless of extension
_ALWAYS_IGNORE = [
    # LaTeX compile intermediates
    "*.aux", "*.log", "*.out", "*.toc", "*.lof", "*.lot", "*.loa",
    "*.fls", "*.fdb_latexmk", "*.synctex.gz", "*.synctex",
    "*.blg", "*.bbl", "*.bcf", "*.run.xml",
    "*.nav", "*.snm", "*.vrb",
    "*.nlo", "*.nls", "*.ilg", "*.ind", "*.idx",
    "*.glo", "*.gls", "*.glg", "*.ist",
    "*.acn", "*.acr", "*.alg",
    "*.xdv", "*.dvi", "*.ps",
    "*-blx.bib", "*.@bstract",
    # minitoc
    "*.maf", "*.mtc", "*.mtc0", "*.mtc1", "*.mtc2", "*.mtc3",
    "*.mlf", "*.mlt",
    # Archive / compressed
    "*.tar.gz", "*.tar", "*.zip", "*.rar", "*.7z",
    # Overleaf internal / metadata
    "00README.json",
    # Common non-LaTeX junk
    "*.pyc", "*.DS_Store", "*.py", "*.json", "*.md", "*.yaml", "*.yml",
    "*.sh", "*.toml",
    ".git/", ".gitignore", "__pycache__/", ".overleaf/",
]

# Regex for \input, \include, \bibliography, \includegraphics, etc.
_TEX_INCLUDE_RE = re.compile(
    r"\\(?:input|include|bibliography|addbibresource|includegraphics"
    r"|lstinputlisting|verbatiminput)\s*(?:\[.*?\])?\s*\{([^}]+)\}"
)


def _scan_tex_deps(project_dir: Path) -> set[str]:
    """Scan all .tex files for referenced files (figures, bibs, inputs).

    Returns a set of relative paths that are explicitly referenced.
    """
    deps: set[str] = set()
    for tex_file in project_dir.rglob("*.tex"):
        try:
            content = tex_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for match in _TEX_INCLUDE_RE.finditer(content):
            ref = match.group(1).strip()
            # Handle comma-separated (e.g. \bibliography{ref1,ref2})
            for part in ref.split(","):
                part = part.strip()
                if part:
                    deps.add(part)
    return deps


def _is_essential(rel_path: str, project_dir: Path) -> bool:
    """Check if a file has an essential LaTeX extension."""
    return Path(rel_path).suffix.lower() in _ESSENTIAL_EXTS


def load_patterns(project_dir: Path) -> tuple[list[str], list[str]]:
    """Load ignore and negation patterns from .overleafignore, merged with defaults.

    Returns (ignore_patterns, negation_patterns). Lines starting with '!' are
    negation patterns that override ignore rules (like .gitignore).
    """
    ignore = list(_ALWAYS_IGNORE)
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


def _is_compile_output_pdf(rel_path: str, project_dir: Path) -> bool:
    """Detect PDFs that are likely compile output (not figure assets).

    A PDF is considered compile output if a .tex file with the same stem
    exists in the same directory (e.g. main.pdf next to main.tex).
    """
    p = Path(rel_path)
    if p.suffix.lower() != ".pdf":
        return False
    tex_sibling = (project_dir / p).with_suffix(".tex")
    return tex_sibling.exists()


def is_ignored(rel_path: str, patterns: list[str] | tuple[list[str], list[str]],
               *, project_dir: Path | None = None) -> bool:
    """Check if a relative path should be excluded from upload.

    Uses a whitelist-first strategy:
    1. Negation patterns (!) always force-include.
    2. Explicit ignore patterns always exclude.
    3. Compile-output PDFs (matching a .tex sibling) are excluded.
    4. Files with essential LaTeX extensions are included.
    5. Everything else is excluded.

    Accepts either a flat list (legacy) or a (ignore, negate) tuple.
    """
    # Support both old (flat list) and new (tuple) signatures
    if isinstance(patterns, tuple):
        ignore_patterns, negate_patterns = patterns
    else:
        ignore_patterns, negate_patterns = patterns, []

    parts = Path(rel_path).parts
    filename = Path(rel_path).name
    proj = project_dir or Path(".")

    # 1. Check negation first — if a file matches a negation pattern, it is NOT ignored
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

    # 2. Check explicit ignore patterns (compile artifacts, junk, etc.)
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

    # 3. Exclude compile-output PDFs (e.g. main.pdf when main.tex exists)
    if _is_compile_output_pdf(rel_path, proj):
        return True

    # 4. Whitelist: files with essential LaTeX extensions are included
    if _is_essential(rel_path, proj):
        return False

    # 5. Everything else is excluded
    return True
