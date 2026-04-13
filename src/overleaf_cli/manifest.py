"""Local manifest management for sync state tracking."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

MANIFEST_DIR = ".overleaf"
MANIFEST_FILE = "manifest.json"


def hash_file(path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def hash_content(content: str | bytes) -> str:
    """Compute SHA-256 hash of content."""
    if isinstance(content, str):
        content = content.encode("utf-8")
    return hashlib.sha256(content).hexdigest()


class Manifest:
    """Tracks the sync state between local and remote."""

    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.manifest_dir = project_dir / MANIFEST_DIR
        self.manifest_path = self.manifest_dir / MANIFEST_FILE
        self.data = self._load()

    def _load(self) -> dict:
        if self.manifest_path.exists():
            return json.loads(self.manifest_path.read_text())
        return {
            "project_id": "",
            "project_name": "",
            "base_url": "",
            "last_sync": "",
            "files": {},
        }

    def save(self):
        self.manifest_dir.mkdir(parents=True, exist_ok=True)
        self.data["last_sync"] = datetime.now(timezone.utc).isoformat()
        self.manifest_path.write_text(json.dumps(self.data, indent=2, ensure_ascii=False))

    @property
    def project_id(self) -> str:
        return self.data.get("project_id", "")

    @property
    def base_url(self) -> str:
        return self.data.get("base_url", "")

    def init(self, project_id: str, project_name: str, base_url: str):
        self.data["project_id"] = project_id
        self.data["project_name"] = project_name
        self.data["base_url"] = base_url

    def set_file(self, rel_path: str, file_id: str, file_type: str, content_hash: str):
        self.data["files"][rel_path] = {
            "id": file_id,
            "type": file_type,
            "hash": content_hash,
        }

    def remove_file(self, rel_path: str):
        self.data["files"].pop(rel_path, None)

    def get_file(self, rel_path: str) -> dict | None:
        return self.data["files"].get(rel_path)

    def all_files(self) -> dict[str, dict]:
        return self.data.get("files", {})

    def get_local_changes(self, ignore_fn=None) -> tuple[list[str], list[str], list[str]]:
        """Compare local files against manifest.
        Returns (added, modified, deleted) relative paths.
        ignore_fn: optional callable(rel_path) -> bool, to skip ignored files.
        """
        added, modified, deleted = [], [], []
        manifest_files = set(self.all_files().keys())
        local_files = set()

        for path in self.project_dir.rglob("*"):
            if path.is_dir():
                continue
            rel = str(path.relative_to(self.project_dir))
            if rel.startswith(MANIFEST_DIR):
                continue
            if ignore_fn and ignore_fn(rel):
                continue
            local_files.add(rel)
            entry = self.get_file(rel)
            if entry is None:
                added.append(rel)
            elif hash_file(path) != entry["hash"]:
                modified.append(rel)

        for rel in manifest_files - local_files:
            if ignore_fn and ignore_fn(rel):
                continue
            deleted.append(rel)

        return sorted(added), sorted(modified), sorted(deleted)
