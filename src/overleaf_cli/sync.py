"""Bidirectional sync logic between local and Overleaf."""

from pathlib import Path

import click

from overleaf_cli.client import OverleafClient
from overleaf_cli.manifest import Manifest, hash_file, hash_content
from overleaf_cli.project import (
    get_file_tree,
    download_file,
    upload_file,
    create_folder,
    delete_entity,
    get_root_folder_id,
)
from overleaf_cli.socketio import SocketIOClient


def clone_project(client: OverleafClient, cookie_value: str,
                  project_id: str, project_name: str, base_url: str,
                  target_dir: Path):
    """Clone a project from Overleaf to local directory."""
    target_dir.mkdir(parents=True, exist_ok=True)
    manifest = Manifest(target_dir)
    manifest.init(project_id, project_name, base_url)

    sio = SocketIOClient(cookie_value, base_url)
    try:
        sio.connect(project_id)
        entries = get_file_tree(sio, project_id)

        for entry in entries:
            rel_path = entry["path"]
            local_path = target_dir / rel_path
            local_path.parent.mkdir(parents=True, exist_ok=True)

            if entry["type"] == "doc":
                content = sio.get_doc_content(entry["id"])
                sio.leave_doc(entry["id"])
                local_path.write_text(content, encoding="utf-8")
                content_hash = hash_content(content)
            else:
                data = download_file(client, project_id, entry["id"])
                local_path.write_bytes(data)
                content_hash = hash_content(data)

            manifest.set_file(rel_path, entry["id"], entry["type"], content_hash)
            click.echo(f"  {rel_path}")
    finally:
        sio.disconnect()

    manifest.save()


def pull(client: OverleafClient, cookie_value: str, manifest: Manifest):
    """Pull remote changes to local."""
    project_id = manifest.project_id
    base_url = manifest.base_url

    sio = SocketIOClient(cookie_value, base_url)
    try:
        sio.connect(project_id)
        remote_entries = get_file_tree(sio, project_id)
        remote_map = {e["path"]: e for e in remote_entries}
        local_files = manifest.all_files()

        # Find remote additions and modifications
        for rel_path, entry in remote_map.items():
            local_path = manifest.project_dir / rel_path
            local_path.parent.mkdir(parents=True, exist_ok=True)

            if entry["type"] == "doc":
                content = sio.get_doc_content(entry["id"])
                sio.leave_doc(entry["id"])
                content_hash = hash_content(content)
                old = manifest.get_file(rel_path)
                if old is None:
                    local_path.write_text(content, encoding="utf-8")
                    manifest.set_file(rel_path, entry["id"], "doc", content_hash)
                    click.echo(f"  + {rel_path}")
                elif old["hash"] != content_hash:
                    # Check for conflict
                    if local_path.exists() and hash_file(local_path) != old["hash"]:
                        click.echo(f"  ! CONFLICT: {rel_path} (both sides changed)")
                        conflict_path = local_path.with_suffix(local_path.suffix + ".local")
                        conflict_path.write_text(local_path.read_text(encoding="utf-8"), encoding="utf-8")
                        click.echo(f"    Local version saved as {conflict_path.name}")
                    local_path.write_text(content, encoding="utf-8")
                    manifest.set_file(rel_path, entry["id"], "doc", content_hash)
                    click.echo(f"  M {rel_path}")
            else:
                data = download_file(client, project_id, entry["id"])
                content_hash = hash_content(data)
                old = manifest.get_file(rel_path)
                if old is None:
                    local_path.write_bytes(data)
                    manifest.set_file(rel_path, entry["id"], "file", content_hash)
                    click.echo(f"  + {rel_path}")
                elif old["hash"] != content_hash:
                    if local_path.exists() and hash_file(local_path) != old["hash"]:
                        click.echo(f"  ! CONFLICT: {rel_path} (both sides changed)")
                        conflict_path = local_path.with_suffix(local_path.suffix + ".local")
                        conflict_path.write_bytes(local_path.read_bytes())
                        click.echo(f"    Local version saved as {conflict_path.name}")
                    local_path.write_bytes(data)
                    manifest.set_file(rel_path, entry["id"], "file", content_hash)
                    click.echo(f"  M {rel_path}")

        # Find remote deletions
        for rel_path in list(local_files.keys()):
            if rel_path not in remote_map:
                local_path = manifest.project_dir / rel_path
                if local_path.exists():
                    local_path.unlink()
                manifest.remove_file(rel_path)
                click.echo(f"  - {rel_path}")
    finally:
        sio.disconnect()

    manifest.save()


def push(client: OverleafClient, cookie_value: str, manifest: Manifest):
    """Push local changes to remote."""
    project_id = manifest.project_id
    base_url = manifest.base_url
    added, modified, deleted = manifest.get_local_changes()

    if not added and not modified and not deleted:
        click.echo("Nothing to push.")
        return

    # Get root folder id for uploads
    sio = SocketIOClient(cookie_value, base_url)
    try:
        sio.connect(project_id)
        root_folder_id = get_root_folder_id(sio, project_id)
        remote_entries = get_file_tree(sio, project_id)
    finally:
        sio.disconnect()

    # Build folder id map from remote tree
    # For now, upload everything to root (flat). TODO: handle subfolders properly
    remote_map = {e["path"]: e for e in remote_entries}

    # Upload new and modified files
    for rel_path in added + modified:
        local_path = manifest.project_dir / rel_path
        # Determine target folder
        parts = Path(rel_path).parts
        folder_id = root_folder_id
        if len(parts) > 1:
            # Need to ensure parent folders exist
            folder_id = _ensure_folders(client, project_id, root_folder_id,
                                         parts[:-1], remote_entries)

        # If file exists remotely, delete first (overwrite)
        if rel_path in remote_map:
            entry = remote_map[rel_path]
            try:
                delete_entity(client, project_id, entry["type"], entry["id"])
            except Exception:
                pass  # May fail if already deleted

        upload_file(client, project_id, folder_id, local_path, parts[-1])
        content_hash = hash_file(local_path)
        file_type = "doc" if local_path.suffix in (".tex", ".bib", ".cls", ".sty", ".bst", ".txt", ".md") else "file"
        manifest.set_file(rel_path, "", file_type, content_hash)
        prefix = "+" if rel_path in added else "M"
        click.echo(f"  {prefix} {rel_path}")

    # Delete remote files that were deleted locally
    for rel_path in deleted:
        if rel_path in remote_map:
            entry = remote_map[rel_path]
            try:
                delete_entity(client, project_id, entry["type"], entry["id"])
                click.echo(f"  - {rel_path}")
            except Exception as e:
                click.echo(f"  ! Failed to delete {rel_path}: {e}")
        manifest.remove_file(rel_path)

    manifest.save()


def _ensure_folders(client: OverleafClient, project_id: str,
                    root_folder_id: str, folder_parts: tuple,
                    remote_entries: list) -> str:
    """Ensure folder path exists, creating as needed. Return leaf folder ID."""
    # Build existing folder map from remote entries
    # This is approximate — we'd need the full tree with folder IDs
    # For now, try to create and handle "already exists" gracefully
    current_id = root_folder_id
    current_path = ""
    for part in folder_parts:
        current_path = f"{current_path}{part}/" if current_path else f"{part}/"
        try:
            new_id = create_folder(client, project_id, current_id, part)
            if new_id:
                current_id = new_id
        except Exception:
            # Folder likely already exists — try to find its ID from remote tree
            # Fallback: use root folder (files will be flat)
            pass
    return current_id


def status(cookie_value: str, manifest: Manifest):
    """Show local and remote changes."""
    added, modified, deleted = manifest.get_local_changes()

    if added or modified or deleted:
        click.echo("Local changes:")
        for p in added:
            click.echo(f"  + {p}")
        for p in modified:
            click.echo(f"  M {p}")
        for p in deleted:
            click.echo(f"  - {p}")
    else:
        click.echo("No local changes.")

    # Check remote changes
    click.echo("\nChecking remote...")
    project_id = manifest.project_id
    base_url = manifest.base_url
    sio = SocketIOClient(cookie_value, base_url)
    try:
        sio.connect(project_id)
        remote_entries = get_file_tree(sio, project_id)
    finally:
        sio.disconnect()

    remote_map = {e["path"]: e for e in remote_entries}
    local_files = manifest.all_files()

    remote_added = [p for p in remote_map if p not in local_files]
    remote_deleted = [p for p in local_files if p not in remote_map]
    # Can't easily detect remote modifications without downloading content

    if remote_added or remote_deleted:
        click.echo("Remote changes:")
        for p in remote_added:
            click.echo(f"  + {p}")
        for p in remote_deleted:
            click.echo(f"  - {p}")
    else:
        click.echo("No remote structural changes detected.")
        click.echo("(Run 'overleaf pull' to check for content changes)")
