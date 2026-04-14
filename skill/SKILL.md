---
name: overleaf-cli
description: Manage Overleaf LaTeX projects from the terminal. Create, clone, pull, push, and sync projects with Overleaf. Use when the user mentions Overleaf, wants to sync LaTeX to Overleaf, create an Overleaf project, or push/pull from Overleaf.
---

# /overleaf — Overleaf Project Management

Sync LaTeX projects between local filesystem and Overleaf (overleaf.com).

## Prerequisites

- `overleaf` CLI installed: `uv tool install git+https://github.com/zixuzixu/overleaf-cli`
- User must have run `overleaf login` (session stored in `~/.config/overleaf-cli/session.json`)

Check if installed: `which overleaf`. If not found, install it first.

## Commands

```bash
overleaf login                  # authenticate (browser cookie or manual paste)
overleaf projects               # list all projects (ID, name, date)
overleaf clone <project_id>     # download project to local dir
overleaf create "Project Name"  # create new Overleaf project from current dir
overleaf init <project_id>      # link current dir to existing project
overleaf status                 # show local changes (no network, fast)
overleaf pull                   # pull remote changes
overleaf push                   # push via git bridge (preserves URL + collaborators)
overleaf deps                   # scan tex dependencies, preview .overleafignore
overleaf deps --write           # scan and write .overleafignore
overleaf deps --root paper.tex  # use a different root tex file
```

## Workflow: Push LaTeX to Overleaf (IMPORTANT)

When the user asks to "put this on Overleaf", "upload to Overleaf", or "create Overleaf project":

1. Check if already linked: look for `.overleaf/manifest.json` in the project dir
2. **Always generate .overleafignore first** — this ensures only necessary files are uploaded:
   ```bash
   cd <latex_project_dir>
   overleaf deps --write           # scan main.tex deps, write whitelist
   overleaf create "Project Name"  # upload only whitelisted files
   ```
3. If already linked and user made changes:
   ```bash
   overleaf deps --write   # refresh whitelist if tex deps changed
   overleaf status          # check what changed
   overleaf push            # push changes
   ```

**Why `overleaf deps` matters:** Without it, any file with a LaTeX-related extension
gets uploaded (including unused .sty, .bst, extra .tex files). `overleaf deps` scans
`\input`, `\usepackage`, `\bibliography`, `\includegraphics` etc. from the root tex
file and generates a precise whitelist. Only files actually referenced get uploaded.

## Workflow: Get Project from Overleaf

```bash
overleaf projects               # list all, find the ID
overleaf clone <project_id>     # download to local dir
```

## Workflow: Sync Before Editing

```bash
cd <project_dir>
overleaf pull     # get latest changes from collaborators
# ... make edits ...
overleaf push     # push back
```

## How .overleafignore Works

`overleaf deps --write` generates a whitelist-mode `.overleafignore`:

```
# Ignore everything by default
*

# LaTeX source
!main.tex
!math_commands.tex

# Bibliography
!references.bib

# Style/class files (local, not on Overleaf)
!neurips_2024.sty

# Figures
!figures/
!figures/plot1.pdf
!figures/plot2.pdf
```

This means ONLY the listed files are uploaded. To add extra files, append `!path/to/file`.

## Auth Notes

- **Cookie auth** (login/projects/clone/create/pull): stored in `~/.config/overleaf-cli/session.json`
- **Git token** (push only): first push prompts for token from Overleaf Account Settings → Git Integration
- If auth fails, tell user to run `overleaf login` (for cookie) or re-enter git token on next push

## Error Recovery

- "Not logged in" → `overleaf login`
- "Session expired" → `overleaf login`
- "Git authentication failed" → re-run `overleaf push`, enter new token
- "Not in an Overleaf project" → `overleaf clone <id>` or `overleaf init <id>`
