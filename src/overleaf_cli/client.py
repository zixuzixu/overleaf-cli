"""Overleaf HTTP client with cookie auth and CSRF handling."""

import requests
from bs4 import BeautifulSoup

from overleaf_cli.auth import COOKIE_NAME
from overleaf_cli.config import DEFAULT_BASE_URL


class OverleafClient:
    """HTTP client for Overleaf web API."""

    def __init__(self, cookie_value: str, base_url: str = DEFAULT_BASE_URL):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.cookies.set(COOKIE_NAME, cookie_value, domain=".overleaf.com")
        self._csrf_cache: dict[str, str] = {}  # project_id -> token

    def get(self, path: str, **kwargs) -> requests.Response:
        resp = self.session.get(self.base_url + path, **kwargs)
        resp.raise_for_status()
        return resp

    def post(self, path: str, project_id: str | None = None, **kwargs) -> requests.Response:
        if project_id:
            headers = kwargs.pop("headers", {})
            headers["x-csrf-token"] = self._get_csrf(project_id)
            kwargs["headers"] = headers
        resp = self.session.post(self.base_url + path, **kwargs)
        resp.raise_for_status()
        return resp

    def delete(self, path: str, project_id: str, **kwargs) -> requests.Response:
        headers = kwargs.pop("headers", {})
        headers["x-csrf-token"] = self._get_csrf(project_id)
        kwargs["headers"] = headers
        resp = self.session.delete(self.base_url + path, **kwargs)
        resp.raise_for_status()
        return resp

    def _get_csrf(self, project_id: str) -> str:
        if project_id in self._csrf_cache:
            return self._csrf_cache[project_id]
        resp = self.session.get(f"{self.base_url}/project/{project_id}", timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        meta = soup.find("meta", {"name": "ol-csrfToken"})
        if not meta or not meta.get("content"):
            raise RuntimeError("Could not extract CSRF token from project page.")
        token = meta["content"]
        self._csrf_cache[project_id] = token
        return token

    def get_cookie_value(self) -> str:
        for c in self.session.cookies:
            if c.name == COOKIE_NAME:
                return c.value
        raise RuntimeError("Cookie not found in session.")
