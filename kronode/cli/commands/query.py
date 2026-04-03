"""kronode query — test get_context from the terminal."""
import asyncio

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


@click.command()
@click.argument("task_description")
@click.option("--files", "-f", multiple=True, help="File paths you plan to touch")
def query(task_description: str, files: tuple[str, ...]):
    """Test get_context from the terminal.

    Example: kronode query "fix timezone in bookings" -f apps/web/booking.tsx
    """
    asyncio.run(_query(task_description, list(files)))


async def _query(task_description: str, files: list[str]):
    from kronode.core.config import get_settings
    from kronode.core.database import init_db
    from kronode.mcp.server import configure, get_context

    await init_db()
    settings = get_settings()
    configure(org_id=settings.org_id)

    with console.status("[bold]Fetching context..."):
        result = await get_context(task_description, files or None)

    # Action plan
    plan = result.get("action_plan", "")
    if plan:
        console.print(Panel(plan, title="Action Plan", border_style="green"))

    # Top conventions
    top = result.get("top_conventions", [])
    if top:
        table = Table(title="Top Conventions", show_lines=True)
        table.add_column("Score", style="cyan", width=6)
        table.add_column("Rule", style="white")
        table.add_column("Reason", style="dim")
        for c in top:
            table.add_row(
                str(c.get("relevance_score", "")),
                c["rule"][:100],
                c.get("match_reason", "")[:50],
            )
        console.print(table)

    # Issues
    direct = result.get("directly_related_issues", [])
    if direct:
        console.print("\n[bold]Directly Related Issues[/bold]")
        for i in direct:
            console.print(f"  [{i.get('similarity', '')}] {i['title'][:70]}")
            console.print(f"    [dim]{i.get('url', '')}[/dim]")

    loose = result.get("loosely_related_issues", [])
    if loose:
        console.print("\n[bold dim]Loosely Related[/bold dim]")
        for i in loose[:3]:
            console.print(f"  [dim][{i.get('similarity', '')}] {i['title'][:70]}[/dim]")

    # Docs
    docs = result.get("relevant_documentation", [])
    if docs:
        console.print("\n[bold]Documentation[/bold]")
        for d in docs[:3]:
            console.print(f"  {d['heading'][:60]}")

    # Files to check
    files_check = result.get("files_you_should_also_check", [])
    if files_check:
        console.print("\n[bold]Also Check[/bold]")
        for f in files_check:
            console.print(f"  {f['file']} — {f['reason']}")

    # Other conventions count
    other = result.get("other_conventions", [])
    if other:
        console.print(f"\n[dim]{len(other)} more conventions available[/dim]")
