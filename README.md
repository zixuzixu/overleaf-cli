# overleaf-cli

A Python CLI tool for bidirectional sync with [Overleaf](https://www.overleaf.com). Pull, push, and manage your LaTeX projects from the terminal.

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

# 3. Clone a project
overleaf clone <project_id>

# 4. Work locally, then sync
cd <project_dir>
overleaf status    # see what changed
overleaf pull      # pull remote changes
overleaf push      # push local changes
```

## Commands

| Command | Description |
|---------|-------------|
| `overleaf login` | Authenticate with Overleaf |
| `overleaf logout` | Clear saved session |
| `overleaf projects` | List all your projects |
| `overleaf clone <id>` | Download project to local directory |
| `overleaf pull` | Pull remote changes (run inside project dir) |
| `overleaf push` | Push local changes to Overleaf |
| `overleaf status` | Show local and remote changes |

## Authentication

Overleaf does not provide a public API. This tool uses the `overleaf_session2` cookie for authentication.

**Automatic extraction** (recommended): The tool tries to extract the cookie from your Chrome or Firefox browser using `browser_cookie3`.

**Manual input** (fallback): If automatic extraction fails:
1. Open https://www.overleaf.com and log in
2. Open DevTools (F12) → Application → Cookies → overleaf.com
3. Copy the value of `overleaf_session2`
4. Run `overleaf login` and paste the value

Session is saved to `~/.config/overleaf-cli/session.json`.

## How Sync Works

Each cloned project has a `.overleaf/manifest.json` that tracks file hashes. Sync works by comparing local file hashes against the manifest:

- **pull**: Fetches the remote file tree, downloads files that changed remotely, updates manifest
- **push**: Scans local files for changes vs manifest, uploads changed files, updates manifest
- **Conflicts**: If the same file changed on both sides, the local version is saved as `<file>.local` and the remote version is downloaded

## Development

```bash
git clone https://github.com/zixuzixu/overleaf-cli.git
cd overleaf-cli
uv venv && uv pip install -e ".[dev]"
uv run pytest tests/ -v
```

## Limitations

- **No official API**: All endpoints are reverse-engineered and may change without notice
- **Cookie expiration**: The session cookie expires periodically; re-run `overleaf login` when it does
- **Socket.IO v1**: Reading `.tex` file content requires a Socket.IO v1 WebSocket connection, which is the most fragile part
- **No auto-merge**: Conflicts are reported, not automatically resolved

## License

MIT
