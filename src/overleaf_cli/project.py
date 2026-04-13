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


def get_project_data(client: OverleafClient, project_id: str) -> dict:
    """Get project root folder ID and entity list from project page HTML.
    Returns {root_folder_id: str, entities: {path: {id, type, folder_id}}}.
    """
    resp = client.get(f"/project/{project_id}", timeout=15)
    soup = BeautifulSoup(resp.text, "html.parser")

    # Extract root folder from ol-rootFolder meta tag
    root_meta = soup.find("meta", {"name": "ol-rootFolder"})
    if not root_meta or not root_meta.get("content"):
        # Fallback: try ol-project meta
        proj_meta = soup.find("meta", {"name": "ol-project"})
        if proj_meta and proj_meta.get("content"):
            proj = json.loads(proj_meta["content"])
            root_folder = proj.get("rootFolder", [{}])
            root_id = root_folder[0].get("_id", "") if root_folder else ""
            entities = {}
            if root_folder:
                _walk_folder_entities(root_folder[0], "", entities)
            return {"root_folder_id": root_id, "entities": entities}
        raise RuntimeError("Could not extract project data from page.")

    root_folder_data = json.loads(root_meta["content"])
    root_id = root_folder_data[0]["_id"] if root_folder_data else ""
    entities = {}
    if root_folder_data:
        _walk_folder_entities(root_folder_data[0], "", entities)
    return {"root_folder_id": root_id, "entities": entities}


def _walk_folder_entities(folder: dict, prefix: str, entities: dict):
    """Walk folder tree and build flat entity map."""
    folder_id = folder.get("_id", "")
    for doc in folder.get("docs", []):
        path = f"{prefix}{doc['name']}" if prefix else doc["name"]
        entities[path] = {"id": doc["_id"], "type": "doc", "folder_id": folder_id}
    for f in folder.get("fileRefs", []):
        path = f"{prefix}{f['name']}" if prefix else f["name"]
        entities[path] = {"id": f["_id"], "type": "file", "folder_id": folder_id}
    for sub in folder.get("folders", []):
        sub_prefix = f"{prefix}{sub['name']}/"
        _walk_folder_entities(sub, sub_prefix, entities)


def delete_project(client: OverleafClient, project_id: str):
    """Delete a project on Overleaf."""
    # Need CSRF from dashboard (not project page, since project may be gone)
    resp = client.session.get(client.base_url + "/project", timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    meta = soup.find("meta", {"name": "ol-csrfToken"})
    if not meta or not meta.get("content"):
        raise RuntimeError("Could not get CSRF token.")
    csrf = meta["content"]
    resp = client.session.delete(
        client.base_url + f"/project/{project_id}",
        headers={"x-csrf-token": csrf},
        timeout=15,
    )
    resp.raise_for_status()


def create_project_from_zip(client: OverleafClient, project_name: str,
                            zip_data: bytes) -> str:
    """Create a new project on Overleaf by uploading a zip file.
    Returns the project ID.
    """
    # Need CSRF token from the dashboard page
    resp = client.session.get(client.base_url + "/project", timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    meta = soup.find("meta", {"name": "ol-csrfToken"})
    if not meta or not meta.get("content"):
        raise RuntimeError("Could not get CSRF token for project creation.")
    csrf = meta["content"]

    resp = client.session.post(
        client.base_url + "/project/new/upload",
        headers={"x-csrf-token": csrf},
        files={"qqfile": (f"{project_name}.zip", zip_data, "application/zip")},
        data={
            "name": project_name,
            "relativePath": "null",
            "type": "application/zip",
        },
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    if not data.get("success"):
        raise RuntimeError(f"Project creation failed: {data}")
    project_id = data.get("project_id", "")
    if not project_id:
        raise RuntimeError(f"No project_id in response: {data}")
    return project_id


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
