"""Bidirectional sync logic between local and Overleaf."""

import io
import zipfile
from pathlib import Path

import click

from overleaf_cli.client import OverleafClient
from overleaf_cli.manifest import Manifest, hash_file, hash_content
from overleaf_cli.ignore import load_patterns, is_ignored
from overleaf_cli.project import (
    download_project_zip,
    upload_file,
    create_folder,
    delete_entity,
    get_project_data,
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
    """Push local changes to remote via REST upload."""
    project_id = manifest.project_id
    patterns = load_patterns(manifest.project_dir)
    added, modified, deleted = manifest.get_local_changes(
        ignore_fn=lambda p: is_ignored(p, patterns)
    )

    if not added and not modified and not deleted:
        click.echo("Nothing to push.")
        return

    # Get project data (root folder ID and file tree) from project page
    proj_data = get_project_data(client, project_id)
    root_folder_id = proj_data["root_folder_id"]
    remote_entities = proj_data["entities"]  # {path: {id, type, folder_id}}

    # Upload new and modified files
    for rel_path in added + modified:
        local_path = manifest.project_dir / rel_path
        parts = Path(rel_path).parts
        folder_id = root_folder_id

        if len(parts) > 1:
            folder_id = _ensure_folders(client, project_id, root_folder_id,
                                        parts[:-1], remote_entities)

        # If file exists remotely, delete first (Overleaf doesn't support overwrite)
        if rel_path in remote_entities:
            entity = remote_entities[rel_path]
            try:
                delete_entity(client, project_id, entity["type"], entity["id"])
            except Exception:
                pass

        upload_file(client, project_id, folder_id, local_path, parts[-1])
        content_hash = hash_file(local_path)
        manifest.set_file(rel_path, "", _guess_type(rel_path), content_hash)
        prefix = "+" if rel_path in added else "M"
        click.echo(f"  {prefix} {rel_path}")

    # Delete remote files that were deleted locally
    for rel_path in deleted:
        if rel_path in remote_entities:
            entity = remote_entities[rel_path]
            try:
                delete_entity(client, project_id, entity["type"], entity["id"])
                click.echo(f"  - {rel_path}")
            except Exception as e:
                click.echo(f"  ! Failed to delete {rel_path}: {e}")
        manifest.remove_file(rel_path)

    manifest.save()


def _ensure_folders(client: OverleafClient, project_id: str,
                    root_folder_id: str, folder_parts: tuple,
                    remote_entities: dict) -> str:
    """Ensure folder path exists, creating as needed. Return leaf folder ID."""
    current_id = root_folder_id
    for part in folder_parts:
        try:
            new_id = create_folder(client, project_id, current_id, part)
            if new_id:
                current_id = new_id
        except Exception:
            pass
    return current_id


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
