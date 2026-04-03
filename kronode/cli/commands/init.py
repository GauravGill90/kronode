"""kronode init — set up Kronode for a local repo."""
import os
import asyncio
from pathlib import Path

import click
from rich.console import Console
from rich.prompt import Prompt

from kronode.core.config import KRONODE_DIR, CONFIG_FILE

console = Console()


@click.command()
@click.argument("repo_path", default=".", type=click.Path(exists=True))
def init(repo_path: str):
    """Initialize Kronode for a local git repo.

    REPO_PATH is the path to your git clone (default: current directory).
    """
    repo_path = os.path.abspath(repo_path)
    git_dir = os.path.join(repo_path, ".git")

    if not os.path.isdir(git_dir):
        console.print(f"[red]Not a git repo:[/red] {repo_path}")
        console.print("Run this inside a cloned git repository.")
        raise SystemExit(1)

    console.print(f"\n[bold]Kronode[/bold] — organizational memory for AI coding tools\n")
    console.print(f"  Repo: [cyan]{repo_path}[/cyan]")

    # Detect provider from remote URL
    provider = "github"
    try:
        import subprocess
        result = subprocess.run(
            ["git", "-C", repo_path, "remote", "get-url", "origin"],
            capture_output=True, text=True,
        )
        remote_url = result.stdout.strip()
        if "gitlab" in remote_url:
            provider = "gitlab"
        elif "bitbucket" in remote_url:
            provider = "bitbucket"
        console.print(f"  Provider: [cyan]{provider}[/cyan]")
        console.print(f"  Remote: [dim]{remote_url}[/dim]")
    except Exception:
        pass

    # Detect mode
    mode = "local"
    if os.environ.get("OPENAI_API_KEY"):
        mode = "byok"
        console.print(f"  Mode: [yellow]BYOK[/yellow] (OpenAI key detected)")
    else:
        console.print(f"  Mode: [green]Local[/green] (no API keys needed)")

    # Create config directory
    KRONODE_DIR.mkdir(parents=True, exist_ok=True)

    # Write config
    config_content = f"""mode = "{mode}"

[repo]
path = "{repo_path}"
provider = "{provider}"
# token = ""  # optional — for kronode ingest --with-prs
"""

    if mode == "byok":
        config_content += f"""
[byok]
openai_api_key = "{os.environ.get('OPENAI_API_KEY', '')}"
"""

    CONFIG_FILE.write_text(config_content)
    console.print(f"\n  Config: [dim]{CONFIG_FILE}[/dim]")

    # Initialize database
    from kronode.core.database import init_db
    asyncio.run(init_db())
    console.print(f"  Database: [dim]{KRONODE_DIR / 'kronode.db'}[/dim]")

    console.print(f"\n[green]Ready![/green] Next steps:")
    console.print(f"  kronode ingest          # extract conventions + docs from git history")
    console.print(f"  kronode serve           # start MCP server")
    console.print(f"  kronode setup claude-code  # get config for your AI tool")
    console.print()
