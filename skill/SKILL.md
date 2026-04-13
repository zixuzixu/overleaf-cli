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
```

## Workflow: Push LaTeX to Overleaf

When the user asks to "put this on Overleaf", "upload to Overleaf", or "create Overleaf project":

1. Check if already linked: look for `.overleaf/manifest.json` in the project dir
2. If not linked:
   ```bash
   cd <latex_project_dir>
   overleaf create "Project Name"
   ```
3. If already linked and user made changes:
   ```bash
   overleaf status   # check what changed
   overleaf push     # push changes
   ```

## Workflow: Get Project from Overleaf

When the user asks to "download from Overleaf", "clone Overleaf project":

1. Find the project ID:
   ```bash
   overleaf projects   # list all, find the ID
   ```
2. Clone it:
   ```bash
   overleaf clone <project_id>
   ```

## Workflow: Sync Before Editing

When editing a shared Overleaf project:

```bash
cd <project_dir>
overleaf pull     # get latest changes from collaborators
# ... make edits ...
overleaf push     # push back
```

## Ignore Rules

Compile artifacts (*.pdf, *.aux, *.log, etc.) are auto-ignored. No need to filter manually.
Custom rules: create `.overleafignore` in project root.

## Auth Notes

- **Cookie auth** (login/projects/clone/create/pull): stored in `~/.config/overleaf-cli/session.json`
- **Git token** (push only): first push prompts for token from Overleaf Account Settings → Git Integration
- If auth fails, tell user to run `overleaf login` (for cookie) or re-enter git token on next push

## Error Recovery

- "Not logged in" → `overleaf login`
- "Session expired" → `overleaf login`
- "Git authentication failed" → re-run `overleaf push`, enter new token
- "Not in an Overleaf project" → `overleaf clone <id>` or `overleaf init <id>`
