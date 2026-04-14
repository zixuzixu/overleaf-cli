# overleaf-cli — Agent Documentation

This document describes how AI coding agents (Claude Code, Cursor, Copilot, etc.) should use overleaf-cli to manage Overleaf LaTeX projects.

## Overview

overleaf-cli syncs LaTeX projects between local filesystem and Overleaf (overleaf.com). It uses a **whitelist strategy**: only essential LaTeX files are uploaded by default. No manual filtering needed.

## Prerequisites

- `overleaf` CLI installed: `uv tool install git+https://github.com/zixuzixu/overleaf-cli`
- User must have run `overleaf login` at least once (cookie stored in `~/.config/overleaf-cli/session.json`)
- For push: git token from https://www.overleaf.com/user/settings → Git Integration

## Commands Reference

### Authentication

```bash
overleaf login     # Interactive: extracts browser cookie or prompts for manual input
overleaf logout    # Clears saved session
```

Check if logged in: `overleaf projects` succeeds → logged in. Fails → needs login.

### Project Management

```bash
# List all projects (shows ID, name, last updated)
overleaf projects

# Create new project from current directory
# Only uploads essential LaTeX files (see "What Gets Uploaded" below)
overleaf create "Project Name"

# Clone existing project to local directory
overleaf clone <project_id>
overleaf clone <project_id> --name custom_dir_name

# Link current directory to existing project (no download)
overleaf init <project_id>
```

### Sync Operations

```bash
# Show local changes vs last sync (no network, fast)
overleaf status

# Download remote changes
overleaf pull

# Upload local changes via git bridge
# First push prompts for git token, subsequent pushes use saved token
overleaf push
```

## What Gets Uploaded (Whitelist Strategy)

The CLI uses a whitelist-first approach. Only files with recognized LaTeX extensions are uploaded:

**Included by default:**
- LaTeX source: `.tex`, `.bib`, `.bst`, `.cls`, `.sty`, `.dtx`, `.ins`, `.ltx`, `.def`, `.cfg`, `.fd`
- Figures: `.pdf`, `.png`, `.jpg`, `.jpeg`, `.eps`, `.svg`, `.tikz`
- Data: `.csv`, `.dat`
- Fonts: `.ttf`, `.otf`, `.woff`, `.pfb`, `.afm`, `.tfm`, `.vf`, `.enc`, `.map`

**Excluded by default:**
- Compile artifacts: `*.aux`, `*.log`, `*.out`, `*.bbl`, `*.fls`, `*.synctex.gz`, etc.
- Compile-output PDFs: any `.pdf` with a matching `.tex` sibling (e.g. `main.pdf` is skipped because `main.tex` exists, but `figures/plot.pdf` is uploaded)
- Non-LaTeX files: `*.py`, `*.json`, `*.md`, `*.yaml`, `*.sh`, `*.toml`
- Archives: `*.tar.gz`, `*.zip`, `*.rar`
- System files: `.git/`, `__pycache__/`, `.DS_Store`

**No `.overleafignore` is needed for typical LaTeX projects.** The defaults handle the common case correctly.

## Typical Agent Workflows

### Workflow 1: Create project from local LaTeX files

```bash
cd /path/to/latex/project
overleaf create "Paper Title"
# Only essential files uploaded — no .py, .json, .md, etc.
```

### Workflow 2: Edit existing Overleaf project

```bash
overleaf clone <project_id>
cd <project_dir>
# ... agent edits .tex files ...
overleaf push
```

### Workflow 3: Compile locally, then sync

```bash
cd <project_dir>
# Agent writes/edits .tex files
latexmk -pdf main.tex    # compile locally
overleaf push             # only pushes source files, compile PDFs auto-excluded
```

### Workflow 4: Pull collaborator changes before editing

```bash
cd <project_dir>
overleaf pull             # get latest from Overleaf
# ... agent edits ...
overleaf push
```

## Custom Ignore Rules

For non-standard needs, create `.overleafignore` in project root (gitignore syntax):

```
# Exclude specific directories
drafts/
old_versions/

# Force-include a non-standard file type (negation pattern)
!data/*.xlsx
```

## Project State

Each linked project has `.overleaf/manifest.json`:
```json
{
  "project_id": "...",
  "project_name": "...",
  "base_url": "https://www.overleaf.com",
  "last_sync": "...",
  "files": {
    "main.tex": {"type": "doc", "id": "", "hash": "sha256:..."},
    "figures/fig1.pdf": {"type": "file", "id": "", "hash": "sha256:..."}
  }
}
```

The agent can read this to determine:
- Whether a directory is an Overleaf project (`project_id` is non-empty)
- Which files are tracked
- When the last sync happened

## Error Handling

| Error | Cause | Fix |
|-------|-------|-----|
| "Not logged in" | No session cookie | Run `overleaf login` |
| "Session expired" | Cookie expired | Run `overleaf login` again |
| "Git authentication failed" | Bad git token | Run `overleaf push` again to re-enter token |
| "Not in an Overleaf project" | No `.overleaf/manifest.json` | Run `overleaf clone` or `overleaf init` first |
| "Already linked to project" | `.overleaf/` exists | Remove `.overleaf/` to re-init |

## Notes for Agents

1. **Never edit `.overleaf/manifest.json` directly.** The CLI manages it.
2. **Always `overleaf pull` before editing** if the project has collaborators.
3. **`overleaf status` is free** (no network). Use it to check before push.
4. **Push uses git bridge**, which preserves project URL and collaborator access.
5. **No need to create `.overleafignore`** for typical projects — defaults are correct.
6. **Compile-output PDFs are auto-detected** — `main.pdf` is skipped when `main.tex` exists, but `figures/*.pdf` is uploaded.
