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
DEFAULT_PATTERNS = _ALWAYS_IGNORE = [
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

# Regex patterns for LaTeX dependency scanning
_TEX_FILE_REF_RE = re.compile(
    r"\\(?:input|include|bibliography|addbibresource|includegraphics"
    r"|lstinputlisting|verbatiminput)\s*(?:\[.*?\])?\s*\{([^}]+)\}"
)
_TEX_PACKAGE_RE = re.compile(
    r"\\(?:usepackage|RequirePackage)\s*(?:\[.*?\])?\s*\{([^}]+)\}"
)
_TEX_CLASS_RE = re.compile(
    r"\\documentclass\s*(?:\[.*?\])?\s*\{([^}]+)\}"
)
_TEX_BIBSTYLE_RE = re.compile(
    r"\\bibliographystyle\s*\{([^}]+)\}"
)


def scan_tex_deps(project_dir: Path, root_tex: str = "main.tex") -> set[str]:
    """Scan tex files recursively to find all required files.

    Starting from root_tex, follows \\input/\\include chains and collects:
    - .tex files (via \\input, \\include)
    - .bib files (via \\bibliography, \\addbibresource)
    - .sty files (via \\usepackage — only if local copy exists)
    - .cls files (via \\documentclass — only if local copy exists)
    - .bst files (via \\bibliographystyle — only if local copy exists)
    - figure files (via \\includegraphics — resolved with common extensions)

    Returns a set of relative paths that exist on disk.
    """
    deps: set[str] = set()
    visited: set[str] = set()

    def _resolve(ref: str, extensions: list[str]) -> str | None:
        """Find a file matching ref, trying with given extensions."""
        # Try exact path first
        if (project_dir / ref).is_file():
            return ref
        # Try with extensions
        for ext in extensions:
            candidate = ref if ref.endswith(ext) else ref + ext
            if (project_dir / candidate).is_file():
                return candidate
        return None

    def _scan_file(tex_rel: str) -> None:
        if tex_rel in visited:
            return
        visited.add(tex_rel)

        tex_path = project_dir / tex_rel
        if not tex_path.is_file():
            return

        deps.add(tex_rel)

        try:
            content = tex_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return

        # \input, \include → recurse into .tex files
        for match in _TEX_FILE_REF_RE.finditer(content):
            ref = match.group(1).strip()
            cmd = content[match.start():match.start()+20]

            if "includegraphics" in cmd:
                # Figure: try common image extensions
                resolved = _resolve(ref, [".pdf", ".png", ".jpg", ".jpeg",
                                          ".eps", ".svg", ".tikz"])
                if resolved:
                    deps.add(resolved)
            elif "bibliography" in cmd or "addbibresource" in cmd:
                # Bibliography: comma-separated, .bib extension
                for part in ref.split(","):
                    part = part.strip()
                    if part:
                        resolved = _resolve(part, [".bib"])
                        if resolved:
                            deps.add(resolved)
            else:
                # \input, \include → .tex file, recurse
                resolved = _resolve(ref, [".tex"])
                if resolved:
                    _scan_file(resolved)

        # \usepackage → local .sty files only
        for match in _TEX_PACKAGE_RE.finditer(content):
            for pkg in match.group(1).split(","):
                pkg = pkg.strip()
                if pkg:
                    resolved = _resolve(pkg, [".sty"])
                    if resolved:
                        deps.add(resolved)

        # \documentclass → local .cls file
        for match in _TEX_CLASS_RE.finditer(content):
            cls = match.group(1).strip()
            resolved = _resolve(cls, [".cls"])
            if resolved:
                deps.add(resolved)

        # \bibliographystyle → local .bst file
        for match in _TEX_BIBSTYLE_RE.finditer(content):
            bst = match.group(1).strip()
            resolved = _resolve(bst, [".bst"])
            if resolved:
                deps.add(resolved)

    # Find root tex file
    root_resolved = _resolve(root_tex, [".tex"])
    if root_resolved:
        _scan_file(root_resolved)
    else:
        # Fallback: scan all .tex files
        for tex_file in project_dir.rglob("*.tex"):
            rel = str(tex_file.relative_to(project_dir))
            _scan_file(rel)

    return deps


def generate_overleafignore(project_dir: Path, root_tex: str = "main.tex") -> str:
    """Generate .overleafignore content based on tex dependency analysis.

    Scans root_tex for all dependencies and creates a whitelist-mode
    .overleafignore that only includes required files.
    """
    deps = scan_tex_deps(project_dir, root_tex)

    # Group by type for readable output
    tex_files = sorted(f for f in deps if f.endswith(".tex"))
    bib_files = sorted(f for f in deps if f.endswith(".bib"))
    style_files = sorted(f for f in deps
                         if f.endswith((".sty", ".cls", ".bst")))
    figure_files = sorted(f for f in deps
                          if not f.endswith((".tex", ".bib", ".sty",
                                            ".cls", ".bst")))

    # Build .overleafignore with whitelist mode
    lines = [
        "# Auto-generated by: overleaf deps",
        "# Whitelist mode: ignore everything, then un-ignore required files.",
        "#",
        "# To regenerate: overleaf deps --write",
        "# To add files:  append !path/to/file below",
        "",
        "# Ignore everything by default",
        "*",
        "",
    ]

    if tex_files:
        lines.append("# LaTeX source")
        for f in tex_files:
            lines.append(f"!{f}")
        lines.append("")

    if bib_files:
        lines.append("# Bibliography")
        for f in bib_files:
            lines.append(f"!{f}")
        lines.append("")

    if style_files:
        lines.append("# Style/class files (local, not on Overleaf)")
        for f in style_files:
            lines.append(f"!{f}")
        lines.append("")

    if figure_files:
        # Group figures by directory
        fig_dirs: dict[str, list[str]] = {}
        for f in figure_files:
            d = str(Path(f).parent)
            fig_dirs.setdefault(d, []).append(f)

        lines.append("# Figures")
        for d, files in sorted(fig_dirs.items()):
            if d != ".":
                lines.append(f"!{d}/")
            for f in files:
                lines.append(f"!{f}")
        lines.append("")

    return "\n".join(lines) + "\n"


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

    Uses a whitelist-first strategy with gitignore-style precedence:

    0. If any parent directory of ``rel_path`` is excluded by a directory
       pattern (e.g. ``arxiv_submission/``) and is not re-included by a
       matching directory negation (e.g. ``!arxiv_submission/``), the
       file is excluded. Bare filename negations like ``!main.tex``
       cannot rescue files inside an excluded parent directory — this
       matches gitignore semantics.
    1. Negation patterns (!) force-include matching files.
    2. Explicit ignore patterns exclude matching files.
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

    # 0. Parent-directory exclusion takes precedence over filename negation.
    #    Once a parent is excluded by a directory pattern, only a matching
    #    directory negation can re-include children. This prevents bare
    #    filename rules like `!main.tex` from leaking files out of an
    #    excluded subtree (e.g. `arxiv_submission/main.tex`).
    ignored_dirs = {p.rstrip("/") for p in ignore_patterns if p.endswith("/")}
    negated_dirs = {p.rstrip("/") for p in negate_patterns if p.endswith("/")}
    for ancestor in parts[:-1]:
        if ancestor in ignored_dirs and ancestor not in negated_dirs:
            return True

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
