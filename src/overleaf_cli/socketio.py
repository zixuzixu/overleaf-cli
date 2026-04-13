"""Socket.IO v1 client for reading Overleaf document content."""

import json
import time

import requests
import websocket

from overleaf_cli.auth import COOKIE_NAME


class SocketIOClient:
    """Minimal Socket.IO v1 client for Overleaf."""

    def __init__(self, cookie_value: str, base_url: str = "https://www.overleaf.com"):
        self.base_url = base_url.rstrip("/")
        self.cookie_value = cookie_value
        self.ws = None
        self.sid = None
        self._msg_id = 0
        self._responses: dict[int, list] = {}

    def connect(self, project_id: str):
        """Handshake + WebSocket connect for a project."""
        # Step 1: HTTP handshake to get session id
        t = int(time.time() * 1000)
        hs_url = f"{self.base_url}/socket.io/1/?projectId={project_id}&t={t}"
        resp = requests.get(
            hs_url,
            cookies={COOKIE_NAME: self.cookie_value},
            timeout=15,
        )
        resp.raise_for_status()
        # Response format: "sid:heartbeat_timeout:close_timeout:transports"
        parts = resp.text.split(":")
        self.sid = parts[0]

        # Step 2: WebSocket upgrade
        ws_scheme = "wss" if self.base_url.startswith("https") else "ws"
        ws_host = self.base_url.replace("https://", "").replace("http://", "")
        ws_url = f"{ws_scheme}://{ws_host}/socket.io/1/websocket/{self.sid}?projectId={project_id}"
        self.ws = websocket.create_connection(
            ws_url,
            cookie=f"{COOKIE_NAME}={self.cookie_value}",
            timeout=30,
        )
        # Read the connect message (type 1)
        msg = self.ws.recv()
        if not msg.startswith("1::"):
            raise RuntimeError(f"Unexpected connect message: {msg}")

    def emit(self, event: str, args: list | None = None) -> list:
        """Send an event and wait for acknowledgement."""
        self._msg_id += 1
        mid = self._msg_id
        payload = json.dumps({"name": event, "args": args or []})
        # Socket.IO v1 event with ack: "5:id+::payload"
        frame = f"5:{mid}+::{payload}"
        self.ws.send(frame)

        # Wait for ack (type 6)
        while True:
            raw = self.ws.recv()
            if raw == "2::":
                # Heartbeat — respond with pong
                self.ws.send("2::")
                continue
            if raw.startswith(f"6:::{mid}"):
                # Ack response: "6:::id+[data]" or "6:::id[data]"
                data_str = raw[len(f"6:::{mid}"):]
                if data_str.startswith("+"):
                    data_str = data_str[1:]
                try:
                    return json.loads(data_str)
                except json.JSONDecodeError:
                    return [data_str]
            # Other messages (events from server) — ignore for now

    def join_project(self, project_id: str) -> dict:
        """Join a project and get the file tree."""
        result = self.emit("joinProject", [{"project_id": project_id}])
        # result is [success, project_data, permissions, ...]
        if len(result) >= 2:
            return result[1]  # project data with rootFolder
        return result[0] if result else {}

    def get_doc_content(self, doc_id: str) -> str:
        """Get the text content of a document."""
        result = self.emit("joinDoc", [doc_id, {"encodeRanges": True}])
        # result is [lines, version, updates, ranges]
        if result and isinstance(result[0], list):
            return "\n".join(result[0])
        return str(result[0]) if result else ""

    def leave_doc(self, doc_id: str):
        """Leave a document."""
        self.emit("leaveDoc", [doc_id])

    def disconnect(self):
        """Close the WebSocket connection."""
        if self.ws:
            try:
                self.ws.send("0::")
                self.ws.close()
            except Exception:
                pass
            self.ws = None
