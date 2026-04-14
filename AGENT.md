# overleaf-cli — Agent Documentation

This document describes how AI coding agents (Claude Code, Cursor, Copilot, etc.) should use overleaf-cli to manage Overleaf LaTeX projects.

## Overview

overleaf-cli syncs LaTeX projects between local filesystem and Overleaf (overleaf.com). It uses **dependency-based whitelisting**: scan the root tex file's dependencies, generate a `.overleafignore`, and upload only what's needed.

## Prerequisites

- `overleaf` CLI installed: `uv tool install git+https://github.com/zixuzixu/overleaf-cli`
- User must have run `overleaf login` at least once (cookie stored in `~/.config/overleaf-cli/session.json`)
- For push: git token from https://www.overleaf.com/user/settings → Git Integration

## Commands Reference

```bash
overleaf login                  # authenticate
overleaf logout                 # clear session
overleaf projects               # list all projects (ID, name, date)
overleaf create "Project Name"  # create new project from current dir
overleaf clone <project_id>     # download project to local dir
overleaf init <project_id>      # link current dir to existing project
overleaf status                 # show local changes (no network, fast)
overleaf pull                   # download remote changes
overleaf push                   # upload local changes via git bridge
overleaf deps                   # scan tex deps, preview .overleafignore
overleaf deps --write           # scan and write .overleafignore
overleaf deps -r paper.tex      # use different root tex file
```

## Critical Rule: Always Run `overleaf deps --write` Before Upload

**Every time before `overleaf create` or `overleaf push`, run `overleaf deps --write` first.**

This scans the root tex file (`main.tex` by default) and generates a precise `.overleafignore` that only includes files actually referenced via `\input`, `\usepackage`, `\bibliography`, `\includegraphics`, etc.

Without it, any file with a LaTeX extension gets uploaded — including unused `.sty`, `.bst`, extra `.tex` files, and standard packages that Overleaf already provides.

## Typical Agent Workflows

### Workflow 1: Create project from local LaTeX files

```bash
cd /path/to/latex/project
overleaf deps --write           # scan main.tex deps → .overleafignore
overleaf create "Paper Title"   # upload only required files
```

### Workflow 2: Push changes after editing

```bash
cd <project_dir>
overleaf deps --write           # refresh whitelist if deps changed
overleaf push                   # upload changes
```

### Workflow 3: Clone and edit

```bash
overleaf clone <project_id>
cd <project_dir>
# ... edit .tex files ...
overleaf push
```

### Workflow 4: Different root tex file

```bash
overleaf deps --write --root paper.tex   # if root is not main.tex
overleaf create "Paper Title"
```

## How Dependency Scanning Works

`overleaf deps` starts from the root tex file and recursively follows:

| LaTeX command | What it finds | File types |
|---|---|---|
| `\input{...}`, `\include{...}` | Included tex files (recursive) | `.tex` |
| `\usepackage{...}` | Local style files only (skips standard packages) | `.sty` |
| `\documentclass{...}` | Local class file | `.cls` |
| `\bibliography{...}`, `\addbibresource{...}` | Bibliography databases | `.bib` |
| `\bibliographystyle{...}` | Local bst file | `.bst` |
| `\includegraphics{...}` | Figure files | `.pdf`, `.png`, `.jpg`, `.eps`, `.svg` |

The generated `.overleafignore` uses whitelist mode (`*` to ignore all, then `!file` to un-ignore):

```
*
!main.tex
!math_commands.tex
!references.bib
!neurips_2024.sty
!figures/
!figures/plot.pdf
```

## Project State

Each linked project has `.overleaf/manifest.json` — the agent can read `project_id` and `last_sync` from it. **Never edit this file directly.**

## Error Handling

| Error | Fix |
|-------|-----|
| "Not logged in" / "Session expired" | `overleaf login` |
| "Git authentication failed" | Re-run `overleaf push`, enter new token |
| "Not in an Overleaf project" | `overleaf clone <id>` or `overleaf init <id>` |
| "No dependencies found" | Check root tex file exists, try `--root <file.tex>` |

## Notes for Agents

1. **Always `overleaf deps --write` before upload.** This is the single most important rule.
2. **Never edit `.overleaf/manifest.json` directly.**
3. **Always `overleaf pull` before editing** if the project has collaborators.
4. **`overleaf status` is free** (no network). Use it to check before push.
5. **Push uses git bridge**, preserving project URL and collaborator access.
