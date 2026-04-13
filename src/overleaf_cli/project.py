"""Overleaf project operations: list, file tree, upload, download."""

import json
from io import BytesIO
from pathlib import Path

from bs4 import BeautifulSoup

from overleaf_cli.client import OverleafClient
from overleaf_cli.socketio import SocketIOClient


def list_projects(client: OverleafClient) -> list[dict]:
    """Get all projects for the logged-in user."""
    resp = client.get("/", timeout=15)
    soup = BeautifulSoup(resp.text, "html.parser")
    meta = soup.find("meta", {"name": "ol-prefetchedProjectsBlob"})
    if not meta or not meta.get("content"):
        raise RuntimeError("Could not find project list. Are you logged in?")
    blob = json.loads(meta["content"])
    projects = []
    for p in blob.get("projects", []):
        projects.append({
            "id": p["id"],
            "name": p["name"],
            "lastUpdated": p.get("lastUpdated", ""),
            "owner": p.get("owner", {}).get("email", ""),
        })
    return projects


def download_project_zip(client: OverleafClient, project_id: str) -> bytes:
    """Download entire project as a zip file."""
    resp = client.get(f"/project/{project_id}/download/zip", timeout=60)
    return resp.content


def download_file(client: OverleafClient, project_id: str, file_id: str) -> bytes:
    """Download a binary file (image, pdf, etc.)."""
    resp = client.get(f"/project/{project_id}/file/{file_id}", timeout=30)
    return resp.content


def get_file_tree(sio: SocketIOClient, project_id: str) -> list[dict]:
    """Get the project file tree via Socket.IO.
    Returns a flat list of {path, id, type} entries.
    """
    project_data = sio.join_project(project_id)
    root_folder = project_data.get("rootFolder", [])
    if not root_folder:
        return []
    entries = []
    _walk_folder(root_folder[0], "", entries)
    return entries


def _walk_folder(folder: dict, prefix: str, entries: list):
    """Recursively walk the folder tree."""
    for doc in folder.get("docs", []):
        path = f"{prefix}{doc['name']}" if prefix else doc["name"]
        entries.append({"path": path, "id": doc["_id"], "type": "doc"})

    for f in folder.get("fileRefs", []):
        path = f"{prefix}{f['name']}" if prefix else f["name"]
        entries.append({"path": path, "id": f["_id"], "type": "file", "hash": f.get("hash", "")})

    for sub in folder.get("folders", []):
        sub_prefix = f"{prefix}{sub['name']}/"
        _walk_folder(sub, sub_prefix, entries)


def get_root_folder_id(sio: SocketIOClient, project_id: str) -> str:
    """Get the root folder ID for uploads."""
    project_data = sio.join_project(project_id)
    root_folder = project_data.get("rootFolder", [])
    if root_folder:
        return root_folder[0]["_id"]
    raise RuntimeError("Could not find root folder.")


def upload_file(client: OverleafClient, project_id: str, folder_id: str,
                file_path: Path, remote_name: str | None = None):
    """Upload a file to a project folder."""
    name = remote_name or file_path.name
    with open(file_path, "rb") as f:
        client.post(
            f"/project/{project_id}/upload?folder_id={folder_id}",
            project_id=project_id,
            files={
                "qqfile": (name, f, "application/octet-stream"),
            },
            data={
                "name": name,
                "relativePath": "null",
                "type": "application/octet-stream",
            },
            timeout=30,
        )


def create_folder(client: OverleafClient, project_id: str,
                   parent_folder_id: str, name: str) -> str:
    """Create a folder and return its ID."""
    resp = client.post(
        f"/project/{project_id}/folder",
        project_id=project_id,
        json={"parent_folder_id": parent_folder_id, "name": name},
        timeout=15,
    )
    return resp.json().get("_id", "")


def delete_entity(client: OverleafClient, project_id: str,
                   entity_type: str, entity_id: str):
    """Delete a doc, file, or folder."""
    client.delete(
        f"/project/{project_id}/{entity_type}/{entity_id}",
        project_id=project_id,
        timeout=15,
    )
