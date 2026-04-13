"""Bidirectional sync logic between local and Overleaf."""

import io
import zipfile
from pathlib import Path

import click

from overleaf_cli.client import OverleafClient
from overleaf_cli.manifest import Manifest, hash_file, hash_content
from overleaf_cli.ignore import load_patterns, is_ignored
from overleaf_cli.project import (
    create_project_from_zip,
    download_project_zip,
)

# Text file extensions treated as "doc" type
_DOC_EXTS = frozenset((
    ".tex", ".bib", ".cls", ".sty", ".bst", ".txt", ".md",
    ".bbl", ".cfg", ".def", ".dtx", ".ins", ".ltx",
))


def _guess_type(path: str) -> str:
    return "doc" if Path(path).suffix.lower() in _DOC_EXTS else "file"


def _extract_zip(zip_data: bytes) -> dict[str, bytes]:
    """Extract zip to a dict of {relative_path: content}."""
    result = {}
    with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            result[info.filename] = zf.read(info.filename)
    return result


def clone_project(client: OverleafClient, cookie_value: str,
                  project_id: str, project_name: str, base_url: str,
                  target_dir: Path):
    """Clone a project from Overleaf to local directory via zip download."""
    target_dir.mkdir(parents=True, exist_ok=True)
    manifest = Manifest(target_dir)
    manifest.init(project_id, project_name, base_url)

    click.echo("  Downloading project zip...")
    zip_data = download_project_zip(client, project_id)
    files = _extract_zip(zip_data)

    patterns = load_patterns(target_dir)
    skipped = 0
    for rel_path, data in files.items():
        if is_ignored(rel_path, patterns):
            skipped += 1
            continue
        local_path = target_dir / rel_path
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(data)
        manifest.set_file(rel_path, "", _guess_type(rel_path), hash_content(data))
        click.echo(f"  {rel_path}")

    if skipped:
        click.echo(f"  ({skipped} files skipped by ignore rules)")
    manifest.save()


def pull(client: OverleafClient, cookie_value: str, manifest: Manifest):
    """Pull remote changes by downloading zip and comparing against manifest."""
    project_id = manifest.project_id

    click.echo("  Downloading project zip...")
    zip_data = download_project_zip(client, project_id)
    remote_files = _extract_zip(zip_data)
    local_files = manifest.all_files()
    changed = False

    # New or modified remote files
    for rel_path, data in remote_files.items():
        remote_hash = hash_content(data)
        local_path = manifest.project_dir / rel_path
        old = manifest.get_file(rel_path)

        if old is None:
            # New remote file
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_bytes(data)
            manifest.set_file(rel_path, "", _guess_type(rel_path), remote_hash)
            click.echo(f"  + {rel_path}")
            changed = True
        elif old["hash"] != remote_hash:
            # Remote file changed — check for conflict
            if local_path.exists() and hash_file(local_path) != old["hash"]:
                click.echo(f"  ! CONFLICT: {rel_path} (both sides changed)")
                conflict_path = local_path.with_suffix(local_path.suffix + ".local")
                if _guess_type(rel_path) == "doc":
                    conflict_path.write_text(local_path.read_text(encoding="utf-8"), encoding="utf-8")
                else:
                    conflict_path.write_bytes(local_path.read_bytes())
                click.echo(f"    Local version saved as {conflict_path.name}")
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_bytes(data)
            manifest.set_file(rel_path, "", _guess_type(rel_path), remote_hash)
            click.echo(f"  M {rel_path}")
            changed = True

    # Remote deletions
    for rel_path in list(local_files.keys()):
        if rel_path not in remote_files:
            local_path = manifest.project_dir / rel_path
            if local_path.exists():
                local_path.unlink()
            manifest.remove_file(rel_path)
            click.echo(f"  - {rel_path}")
            changed = True

    if not changed:
        click.echo("  Already up to date.")

    manifest.save()


def push(client: OverleafClient, cookie_value: str, manifest: Manifest):
    """Push local changes via Overleaf git bridge.

    Uses git clone → copy changes → git push. Non-destructive: preserves
    project URL, history, and collaborator access.
    """
    import shutil
    import subprocess
    import tempfile

    project_id = manifest.project_id
    base_url = manifest.base_url
    patterns = load_patterns(manifest.project_dir)
    added, modified, deleted = manifest.get_local_changes(
        ignore_fn=lambda p: is_ignored(p, patterns)
    )

    if not added and not modified and not deleted:
        click.echo("Nothing to push.")
        return

    click.echo(f"Changes: {len(added)} added, {len(modified)} modified, {len(deleted)} deleted")

    # Get git credentials
    from overleaf_cli.config import load_git_auth, save_git_auth
    git_auth = load_git_auth()
    if not git_auth:
        click.echo(
            "\nGit bridge token required for push.\n"
            "Get your token at: https://www.overleaf.com/user/settings\n"
            "  → 'Git Integration' section → 'Generate token'\n"
        )
        token = click.prompt("Git authentication token", hide_input=True)
        save_git_auth("git", token)
        git_auth = {"email": "git", "token": token}

    from urllib.parse import quote
    token_encoded = quote(git_auth["token"], safe="")
    git_url = f"https://git:{token_encoded}@git.overleaf.com/{project_id}"

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir) / "repo"

        # Clone current state from Overleaf
        click.echo("  Cloning from Overleaf git...")
        r = subprocess.run(
            ["git", "clone", git_url, str(tmp)],
            capture_output=True, text=True, timeout=60,
        )
        if r.returncode != 0:
            err = r.stderr.strip()
            if "Authentication failed" in err or "403" in err:
                click.echo("  Git authentication failed. Check your email and token.")
                click.echo("  Re-run 'overleaf push' to enter new credentials.")
                from overleaf_cli.config import load_session
                session = load_session()
                if session:
                    session.pop("git_email", None)
                    session.pop("git_token", None)
                    from overleaf_cli.config import SESSION_FILE
                    import json
                    SESSION_FILE.write_text(json.dumps(session, indent=2))
                raise click.ClickException("Git authentication failed.")
            raise click.ClickException(f"Git clone failed: {err}")

        # Apply local changes to the git working tree
        # Remove all tracked files first (to handle deletions)
        for item in tmp.iterdir():
            if item.name == ".git":
                continue
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()

        # Copy all local non-ignored files
        for path in sorted(manifest.project_dir.rglob("*")):
            if path.is_dir():
                continue
            rel = str(path.relative_to(manifest.project_dir))
            if rel.startswith(".overleaf") or rel.startswith("."):
                continue
            if is_ignored(rel, patterns):
                continue
            dest = tmp / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)

        # Git add, commit, push
        subprocess.run(["git", "add", "-A"], cwd=tmp, capture_output=True, timeout=30)

        # Check if there are actual changes to commit
        r = subprocess.run(
            ["git", "status", "--porcelain"], cwd=tmp,
            capture_output=True, text=True, timeout=10,
        )
        if not r.stdout.strip():
            click.echo("  No changes detected by git (remote already up to date).")
            manifest.save()
            return

        subprocess.run(
            ["git", "commit", "-m", "Update from overleaf-cli"],
            cwd=tmp, capture_output=True, text=True, timeout=30,
        )

        click.echo("  Pushing to Overleaf...")
        r = subprocess.run(
            ["git", "push"], cwd=tmp,
            capture_output=True, text=True, timeout=120,
        )
        if r.returncode != 0:
            raise click.ClickException(f"Git push failed: {r.stderr.strip()}")

    # Update manifest with current file hashes
    manifest.data["files"] = {}
    for path in sorted(manifest.project_dir.rglob("*")):
        if path.is_dir():
            continue
        rel = str(path.relative_to(manifest.project_dir))
        if rel.startswith(".overleaf") or rel.startswith("."):
            continue
        if is_ignored(rel, patterns):
            continue
        manifest.set_file(rel, "", _guess_type(rel), hash_file(path))

    manifest.save()
    for p in added:
        click.echo(f"  + {p}")
    for p in modified:
        click.echo(f"  M {p}")
    for p in deleted:
        click.echo(f"  - {p}")
    click.echo(f"\nPushed to: {base_url}/project/{project_id}")


def status(cookie_value: str, manifest: Manifest):
    """Show local changes (fast, no network). Use pull to check remote."""
    patterns = load_patterns(manifest.project_dir)
    added, modified, deleted = manifest.get_local_changes(
        ignore_fn=lambda p: is_ignored(p, patterns)
    )

    if added or modified or deleted:
        click.echo("Local changes:")
        for p in added:
            click.echo(f"  + {p}")
        for p in modified:
            click.echo(f"  M {p}")
        for p in deleted:
            click.echo(f"  - {p}")
        click.echo(f"\n{len(added)} added, {len(modified)} modified, {len(deleted)} deleted")
    else:
        click.echo("No local changes.")

    click.echo("\n(Run 'overleaf pull' to check for remote changes)")


def init_project(project_id: str, project_name: str, base_url: str,
                 project_dir: Path):
    """Initialize current directory as an Overleaf project (link to existing project)."""
    manifest = Manifest(project_dir)
    if manifest.project_id:
        raise click.ClickException(
            f"Already linked to project '{manifest.project_id}'. "
            "Remove .overleaf/ to re-init."
        )
    manifest.init(project_id, project_name, base_url)

    # Scan local files and record in manifest
    patterns = load_patterns(project_dir)
    count = 0
    for path in sorted(project_dir.rglob("*")):
        if path.is_dir():
            continue
        rel = str(path.relative_to(project_dir))
        if rel.startswith(".overleaf"):
            continue
        if is_ignored(rel, patterns):
            continue
        manifest.set_file(rel, "", _guess_type(rel), hash_file(path))
        click.echo(f"  {rel}")
        count += 1

    manifest.save()
    click.echo(f"\nInitialized with {count} files. Linked to project '{project_id}'.")
    click.echo("Run 'overleaf push' to upload files to Overleaf.")


def create_and_upload(client: OverleafClient, cookie_value: str,
                      project_name: str, base_url: str, project_dir: Path):
    """Create a new project on Overleaf by zipping and uploading local files."""
    manifest = Manifest(project_dir)
    if manifest.project_id:
        raise click.ClickException(
            f"Already linked to project '{manifest.project_id}'. "
            "Remove .overleaf/ to re-init."
        )

    # Collect files to upload (respecting ignore rules)
    patterns = load_patterns(project_dir)
    files_to_upload = []
    for path in sorted(project_dir.rglob("*")):
        if path.is_dir():
            continue
        rel = str(path.relative_to(project_dir))
        if rel.startswith(".overleaf") or rel.startswith("."):
            continue
        if is_ignored(rel, patterns):
            continue
        files_to_upload.append((rel, path))

    if not files_to_upload:
        raise click.ClickException("No files to upload (all files ignored or directory empty).")

    # Create zip from local files
    click.echo(f"Packing {len(files_to_upload)} files...")
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel, path in files_to_upload:
            zf.write(path, rel)
    zip_data = zip_buf.getvalue()

    # Upload zip to create project
    click.echo(f"Creating project '{project_name}' on Overleaf...")
    project_id = create_project_from_zip(client, project_name, zip_data)
    click.echo(f"  Project created: {project_id}")

    # Init manifest with uploaded files
    manifest.init(project_id, project_name, base_url)
    for rel, path in files_to_upload:
        manifest.set_file(rel, "", _guess_type(rel), hash_file(path))
        click.echo(f"  + {rel}")

    manifest.save()
    click.echo(f"\nUploaded {len(files_to_upload)} files.")
    click.echo(f"View at: {base_url}/project/{project_id}")
