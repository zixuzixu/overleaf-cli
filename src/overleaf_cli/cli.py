"""CLI entry point for overleaf-cli."""

from pathlib import Path

import click

from overleaf_cli.auth import get_cookie, login as do_login
from overleaf_cli.client import OverleafClient
from overleaf_cli.config import DEFAULT_BASE_URL, load_session, clear_session
from overleaf_cli.manifest import Manifest
from overleaf_cli.project import list_projects
from overleaf_cli.sync import clone_project, pull, push, status, init_project, create_and_upload


@click.group()
def main():
    """Overleaf CLI — bidirectional sync with Overleaf."""
    pass


@main.command()
def login():
    """Authenticate with Overleaf."""
    do_login()


@main.command()
def logout():
    """Clear saved session."""
    clear_session()
    click.echo("Logged out.")


@main.command()
def projects():
    """List your Overleaf projects."""
    session = load_session()
    base_url = session.get("base_url", DEFAULT_BASE_URL) if session else DEFAULT_BASE_URL
    cookie = get_cookie(base_url)
    client = OverleafClient(cookie, base_url)
    projs = list_projects(client)

    if not projs:
        click.echo("No projects found.")
        return

    click.echo(f"{'ID':<28} {'Name':<40} {'Last Updated':<25}")
    click.echo("-" * 93)
    for p in projs:
        click.echo(f"{p['id']:<28} {p['name']:<40} {p['lastUpdated']:<25}")


@main.command()
@click.argument("project_id")
def init(project_id):
    """Link current directory to an existing Overleaf project."""
    session = load_session()
    base_url = session.get("base_url", DEFAULT_BASE_URL) if session else DEFAULT_BASE_URL
    cookie = get_cookie(base_url)
    client = OverleafClient(cookie, base_url)

    # Look up project name
    projs = list_projects(client)
    match = [p for p in projs if p["id"] == project_id]
    name = match[0]["name"] if match else project_id

    click.echo(f"Linking to project '{name}' ({project_id})...")
    init_project(project_id, name, base_url, Path.cwd())


@main.command()
@click.argument("name")
def create(name):
    """Create a new Overleaf project and upload current directory."""
    session = load_session()
    base_url = session.get("base_url", DEFAULT_BASE_URL) if session else DEFAULT_BASE_URL
    cookie = get_cookie(base_url)
    client = OverleafClient(cookie, base_url)

    create_and_upload(client, cookie, name, base_url, Path.cwd())


@main.command()
@click.argument("project_id")
@click.option("--name", "-n", default=None, help="Local directory name (default: project name)")
def clone(project_id, name):
    """Clone an Overleaf project to local directory."""
    session = load_session()
    base_url = session.get("base_url", DEFAULT_BASE_URL) if session else DEFAULT_BASE_URL
    cookie = get_cookie(base_url)
    client = OverleafClient(cookie, base_url)

    # Get project name if not specified
    if not name:
        projs = list_projects(client)
        match = [p for p in projs if p["id"] == project_id]
        if match:
            name = match[0]["name"].replace(" ", "_").replace("/", "_")
        else:
            name = project_id

    target_dir = Path.cwd() / name
    if target_dir.exists() and any(target_dir.iterdir()):
        raise click.ClickException(f"Directory '{name}' already exists and is not empty.")

    click.echo(f"Cloning project '{project_id}' to '{name}/'...")
    clone_project(client, cookie, project_id, name, base_url, target_dir)
    click.echo(f"Done. Project cloned to '{name}/'.")


def _get_manifest() -> Manifest:
    """Load manifest from current directory."""
    manifest = Manifest(Path.cwd())
    if not manifest.project_id:
        raise click.ClickException(
            "Not in an Overleaf project directory. "
            "Run 'overleaf clone <project_id>' first."
        )
    return manifest


@main.command(name="pull")
def pull_cmd():
    """Pull remote changes from Overleaf."""
    manifest = _get_manifest()
    session = load_session()
    base_url = session.get("base_url", DEFAULT_BASE_URL) if session else DEFAULT_BASE_URL
    cookie = get_cookie(base_url)
    client = OverleafClient(cookie, base_url)

    click.echo("Pulling changes...")
    pull(client, cookie, manifest)
    click.echo("Pull complete.")


@main.command(name="push")
def push_cmd():
    """Push local changes to Overleaf."""
    manifest = _get_manifest()
    session = load_session()
    base_url = session.get("base_url", DEFAULT_BASE_URL) if session else DEFAULT_BASE_URL
    cookie = get_cookie(base_url)
    client = OverleafClient(cookie, base_url)

    click.echo("Pushing changes...")
    push(client, cookie, manifest)
    click.echo("Push complete.")


@main.command(name="status")
def status_cmd():
    """Show local and remote changes."""
    manifest = _get_manifest()
    session = load_session()
    base_url = session.get("base_url", DEFAULT_BASE_URL) if session else DEFAULT_BASE_URL
    cookie = get_cookie(base_url)
    status(cookie, manifest)


@main.command()
@click.option("--write", "-w", is_flag=True, help="Write .overleafignore (default: dry-run)")
@click.option("--root", "-r", default="main.tex", help="Root tex file (default: main.tex)")
def deps(write, root):
    """Scan tex dependencies and generate .overleafignore."""
    from overleaf_cli.ignore import scan_tex_deps, generate_overleafignore, IGNORE_FILE

    project_dir = Path.cwd()
    found = scan_tex_deps(project_dir, root)

    if not found:
        raise click.ClickException(
            f"No dependencies found. Is '{root}' in the current directory?"
        )

    click.echo(f"Found {len(found)} required files from '{root}':")
    for f in sorted(found):
        click.echo(f"  {f}")

    content = generate_overleafignore(project_dir, root)

    if write:
        (project_dir / IGNORE_FILE).write_text(content)
        click.echo(f"\nWrote {IGNORE_FILE}")
    else:
        click.echo(f"\n--- {IGNORE_FILE} (dry-run, use --write to save) ---")
        click.echo(content)


@main.command()
def install():
    """Install AI agent skill for Claude Code / Cursor."""
    from overleaf_cli.skill_content import SKILL_MD

    target_dir = Path.home() / ".claude" / "skills" / "overleaf-cli"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "SKILL.md"
    target.write_text(SKILL_MD)
    click.echo(f"Skill installed to: {target}")
    click.echo("Claude Code can now use the /overleaf skill.")
