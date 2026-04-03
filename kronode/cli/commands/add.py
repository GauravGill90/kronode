"""kronode add — manually add a convention."""
import asyncio

import click
from rich.console import Console

console = Console()


@click.command()
@click.argument("rule")
@click.option("--category", "-c", default="architecture", help="Category: architecture, naming, testing, style, error_handling")
@click.option("--files", "-f", multiple=True, help="Related file paths")
def add(rule: str, category: str, files: tuple[str, ...]):
    """Manually add a convention.

    Example: kronode add "Always use Tamagui styled() for component styling"
    """
    asyncio.run(_add(rule, category, list(files)))


async def _add(rule: str, category: str, files: list[str]):
    from kronode.core.config import get_settings
    from kronode.core.database import init_db, AsyncSessionLocal
    from kronode.models.convention import Convention

    await init_db()
    settings = get_settings()

    async with AsyncSessionLocal() as db:
        db.add(Convention(
            org_id=settings.org_id,
            rule=rule,
            category=category,
            frequency=1,
            confidence=1.0,  # manual = highest confidence
            source_files=files,
            source_prs=[],
            enforced_by=[],
            layer="manual",
        ))
        await db.commit()

    console.print(f"[green]✓[/green] Added: [cyan]{rule}[/cyan]")
    console.print(f"  Category: {category}, Confidence: 1.0")
