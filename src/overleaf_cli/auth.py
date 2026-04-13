"""Authentication: extract or manually input Overleaf session cookie."""

import click
import requests

from overleaf_cli.config import (
    DEFAULT_BASE_URL,
    load_session,
    save_session,
    clear_session,
)

COOKIE_NAME = "overleaf_session2"


def try_browser_cookie() -> str | None:
    """Try to extract overleaf_session2 from browser cookies."""
    try:
        import browser_cookie3
    except ImportError:
        return None

    for loader in [browser_cookie3.chrome, browser_cookie3.firefox]:
        try:
            cj = loader(domain_name=".overleaf.com")
            for c in cj:
                if c.name == COOKIE_NAME:
                    return c.value
        except Exception:
            continue
    return None


def validate_cookie(cookie_value: str, base_url: str = DEFAULT_BASE_URL) -> bool:
    """Check if the cookie is valid by requesting the dashboard."""
    try:
        resp = requests.get(
            base_url + "/project",
            cookies={COOKIE_NAME: cookie_value},
            allow_redirects=False,
            timeout=15,
        )
        # 200 = logged in, 302 to /login = not logged in
        return resp.status_code == 200
    except requests.RequestException:
        return False


def login(base_url: str = DEFAULT_BASE_URL) -> str:
    """Interactive login flow. Returns the cookie value."""
    # Try loading existing session first
    session = load_session()
    if session and validate_cookie(session["cookie"], session.get("base_url", base_url)):
        click.echo("Already logged in (saved session valid).")
        return session["cookie"]

    # Try browser extraction
    click.echo("Attempting to extract cookie from browser...")
    cookie = try_browser_cookie()
    if cookie and validate_cookie(cookie, base_url):
        save_session(cookie, base_url)
        click.echo("Login successful (cookie extracted from browser).")
        return cookie
    elif cookie:
        click.echo("Browser cookie found but invalid/expired.")

    # Manual input fallback
    click.echo(
        "\nManual login required.\n"
        "Steps:\n"
        "  1. Open https://www.overleaf.com in your browser and log in\n"
        "  2. Open DevTools (F12) → Application → Cookies → overleaf.com\n"
        f"  3. Copy the value of '{COOKIE_NAME}'\n"
    )
    cookie = click.prompt("Paste cookie value").strip()

    if not validate_cookie(cookie, base_url):
        raise click.ClickException("Cookie validation failed. Please check and try again.")

    save_session(cookie, base_url)
    click.echo("Login successful.")
    return cookie


def get_cookie(base_url: str = DEFAULT_BASE_URL) -> str:
    """Get a valid cookie, raising if not logged in."""
    session = load_session()
    if not session:
        raise click.ClickException("Not logged in. Run 'overleaf login' first.")
    if not validate_cookie(session["cookie"], session.get("base_url", base_url)):
        clear_session()
        raise click.ClickException("Session expired. Run 'overleaf login' again.")
    return session["cookie"]
