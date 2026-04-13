# overleaf-cli

A Python CLI tool for bidirectional sync with [Overleaf](https://www.overleaf.com). Create, clone, pull, push, and manage your LaTeX projects from the terminal.

## Install

```bash
# Install as a global CLI tool
uv tool install git+https://github.com/zixuzixu/overleaf-cli

# Or install from local source
git clone https://github.com/zixuzixu/overleaf-cli.git
cd overleaf-cli
uv tool install .
```

After installation, the `overleaf` command is available globally.

## Quick Start

```bash
# 1. Login (extracts cookie from browser, or paste manually)
overleaf login

# 2. List your projects
overleaf projects

# 3. Clone an existing project
overleaf clone <project_id>

# 4. Or create a new project from local files
cd my-latex-project/
overleaf create "My Paper"

# 5. Work locally, then sync
overleaf status    # see what changed
overleaf pull      # pull remote changes
overleaf push      # push local changes (via git bridge)
```

## Commands

| Command | Description |
|---------|-------------|
| `overleaf login` | Authenticate with Overleaf (cookie extraction or manual paste) |
| `overleaf logout` | Clear saved session |
| `overleaf projects` | List all your projects |
| `overleaf clone <id>` | Download project to local directory |
| `overleaf create <name>` | Create new Overleaf project from current directory |
| `overleaf init <id>` | Link current directory to an existing project |
| `overleaf pull` | Pull remote changes (run inside project dir) |
| `overleaf push` | Push local changes via git bridge |
| `overleaf status` | Show local changes |
| `overleaf install` | Install AI agent skill for Claude Code / Cursor |

## Authentication

Overleaf does not provide a public API. This tool uses two auth mechanisms:

**Cookie auth** (for clone, pull, create, projects):
- Automatic: extracts `overleaf_session2` from Chrome/Firefox via `browser_cookie3`
- Manual: paste cookie value from DevTools → Application → Cookies
- Saved to `~/.config/overleaf-cli/session.json`

**Git token** (for push):
- Generate at https://www.overleaf.com/user/settings → Git Integration
- First `overleaf push` will prompt for the token, then saves it locally

## Ignore Rules

Files matching `.overleafignore` patterns (or built-in defaults) are skipped during sync.

**Built-in defaults** skip LaTeX compile artifacts: `*.pdf`, `*.aux`, `*.log`, `*.toc`, `*.out`, `*.fls`, `*.fdb_latexmk`, `*.synctex.gz`, `*.bbl`, `*.blg`, `*.nav`, `*.snm`, `*.maf`, `*.mtc*`, archives (`*.tar.gz`, `*.zip`), and Overleaf metadata (`00README.json`).

**Custom rules**: create `.overleafignore` in your project root:
```
# Skip data files
data/
*.csv
# Keep specific PDFs (add to .overleafignore with ! negation... not yet supported)
```

## How Sync Works

Each project has a `.overleaf/manifest.json` tracking file hashes.

- **clone/pull**: Downloads project zip, compares hashes, updates changed files
- **push**: Uses Overleaf git bridge (`git.overleaf.com`) for non-destructive updates. Project URL, history, and collaborators are preserved.
- **create**: Zips local files and uploads via `/project/new/upload` endpoint
- **Conflicts** (pull): If both sides changed a file, local version is saved as `<file>.local`

## AI Agent Integration

Install the overleaf-cli skill so your AI coding agent (Claude Code, Cursor, etc.) can manage Overleaf projects:

```bash
overleaf install
```

This copies a skill definition to `~/.claude/skills/overleaf-cli/SKILL.md`. The agent can then use overleaf commands as part of its workflow (e.g., compile LaTeX locally then push to Overleaf).

See [AGENT.md](AGENT.md) for the full agent-facing documentation.

## Development

```bash
git clone https://github.com/zixuzixu/overleaf-cli.git
cd overleaf-cli
uv venv && uv pip install -e ".[dev]"
uv run pytest tests/ -v
```

## Limitations

- **No official API**: All endpoints are reverse-engineered and may change
- **Cookie expiration**: Session cookie expires periodically, re-run `overleaf login`
- **Push requires git token**: Overleaf premium feature (git bridge)
- **No auto-merge**: Conflicts are reported, not resolved

## License

MIT
