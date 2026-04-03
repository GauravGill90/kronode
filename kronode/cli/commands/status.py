"""kronode status — show ingested data stats."""
import asyncio

import click
from rich.console import Console
from rich.table import Table

console = Console()


@click.command()
def status():
    """Show Kronode data stats — conventions, docs, mode."""
    asyncio.run(_status())


async def _status():
    from kronode.core.config import get_settings
    from kronode.core.database import init_db, AsyncSessionLocal
    from kronode.models.convention import Convention
    from kronode.models.doc_chunk import DocChunk
    from kronode.models.issue_index import IssueIndex
    from sqlalchemy import select, func

    await init_db()
    settings = get_settings()

    async with AsyncSessionLocal() as db:
        convs = (await db.execute(select(func.count(Convention.id)))).scalar() or 0
        docs = (await db.execute(select(func.count(DocChunk.id)))).scalar() or 0

        try:
            issues = (await db.execute(select(func.count(IssueIndex.id)))).scalar() or 0
        except Exception:
            issues = 0

        # Convention categories
        cats = (await db.execute(
            select(Convention.category, func.count(Convention.id)).group_by(Convention.category)
        )).all()

    table = Table(title="Kronode Status")
    table.add_column("", style="bold")
    table.add_column("Value", style="cyan")

    table.add_row("Mode", settings.mode)
    table.add_row("Repo", settings.repo_path or "(not configured)")
    table.add_row("Provider", settings.repo_provider)
    table.add_row("Conventions", str(convs))
    table.add_row("Doc chunks", str(docs))
    table.add_row("Issues indexed", str(issues))

    console.print(table)

    if cats:
        cat_table = Table(title="Conventions by Category")
        cat_table.add_column("Category")
        cat_table.add_column("Count", style="cyan")
        for cat, cnt in sorted(cats, key=lambda x: -x[1]):
            cat_table.add_row(cat, str(cnt))
        console.print(cat_table)
