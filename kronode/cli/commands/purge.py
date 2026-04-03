"""kronode purge — delete all ingested data."""
import asyncio

import click
from rich.console import Console

console = Console()


@click.command()
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
@click.option("--conventions", "only_convs", is_flag=True, help="Only delete conventions")
@click.option("--docs", "only_docs", is_flag=True, help="Only delete doc chunks")
def purge(yes: bool, only_convs: bool, only_docs: bool):
    """Delete all ingested data (conventions, docs, issues).

    Use --conventions or --docs to delete only specific data.
    """
    if not yes:
        what = "conventions" if only_convs else "docs" if only_docs else "all data"
        if not click.confirm(f"Delete {what}? This cannot be undone"):
            return

    asyncio.run(_purge(only_convs, only_docs))


async def _purge(only_convs: bool, only_docs: bool):
    from kronode.core.database import init_db, AsyncSessionLocal
    from sqlalchemy import text

    await init_db()

    async with AsyncSessionLocal() as db:
        if only_convs:
            result = await db.execute(text("DELETE FROM conventions"))
            await db.commit()
            console.print(f"[green]✓[/green] Deleted {result.rowcount} conventions")
        elif only_docs:
            result = await db.execute(text("DELETE FROM doc_chunks"))
            await db.commit()
            console.print(f"[green]✓[/green] Deleted {result.rowcount} doc chunks")
        else:
            tables = ["conventions", "doc_chunks", "issue_index", "memory_records"]
            for t in tables:
                try:
                    result = await db.execute(text(f"DELETE FROM {t}"))
                    console.print(f"  {t}: {result.rowcount} deleted")
                except Exception:
                    pass
            await db.commit()
            console.print(f"[green]✓[/green] All data purged")
