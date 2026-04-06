"""kronode ingest — extract conventions + docs from git history."""
import asyncio
import os
import re
import subprocess

import click
from rich.console import Console
from rich.progress import Progress

console = Console()


def _run_git(repo_path: str, *args) -> str:
    """Run a git command and return stdout."""
    result = subprocess.run(
        ["git", "-C", repo_path, *args],
        capture_output=True, text=True, timeout=30,
    )
    return result.stdout.strip()


def _extract_local_conventions(repo_path: str) -> list[dict]:
    """Extract conventions from local git history — zero network, zero LLM."""
    conventions = []

    # 1. Commit message patterns
    log = _run_git(repo_path, "log", "--oneline", "-200", "--format=%s")
    messages = log.split("\n") if log else []

    # Detect commit prefix patterns (e.g., "feat:", "fix:", "chore:")
    prefix_counts: dict[str, int] = {}
    for msg in messages:
        match = re.match(r"^(\w+)[\(:]", msg)
        if match:
            prefix = match.group(1).lower()
            prefix_counts[prefix] = prefix_counts.get(prefix, 0) + 1

    common_prefixes = [p for p, c in prefix_counts.items() if c >= 5]
    if common_prefixes:
        conventions.append({
            "rule": f"Commit messages use conventional prefixes: {', '.join(common_prefixes)}",
            "category": "naming",
            "source_files": [],
            "source_prs": [],
            "frequency": sum(prefix_counts[p] for p in common_prefixes),
            "confidence": 0.8,
        })

    # 2. File co-change patterns (companions)
    # This is handled by companion_analysis, stored in memory records

    # 3. Directory structure conventions
    top_dirs = _run_git(repo_path, "ls-tree", "-d", "--name-only", "HEAD")
    if top_dirs:
        dirs = [d for d in top_dirs.split("\n") if d and not d.startswith(".")]
        if dirs:
            conventions.append({
                "rule": f"Project structure: top-level directories are {', '.join(dirs[:10])}",
                "category": "architecture",
                "source_files": dirs[:10],
                "source_prs": [],
                "frequency": 1,
                "confidence": 1.0,
            })

    return conventions


def _extract_markdown_docs(repo_path: str) -> list[dict]:
    """Find and read markdown files for doc ingestion."""
    docs = []
    for root, dirs, files in os.walk(repo_path):
        # Skip hidden dirs and node_modules
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in {"node_modules", "dist", "build", ".next", "__pycache__", ".venv"}]

        for f in files:
            if f.endswith((".md", ".mdx")) and not f.startswith("."):
                full_path = os.path.join(root, f)
                rel_path = os.path.relpath(full_path, repo_path)
                try:
                    content = open(full_path).read()
                    if len(content) > 50:
                        docs.append({"path": rel_path, "content": content})
                except Exception:
                    pass

    return docs


def _get_gh_token() -> str | None:
    """Try to get a token from gh CLI (if installed and authenticated)."""
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


@click.command()
@click.option("--with-prs", is_flag=True, help="Also fetch PR review comments (uses gh CLI or --token)")
@click.option("--token", default="", help="GitHub/GitLab/Bitbucket PAT (optional if gh CLI is authenticated)")
def ingest(with_prs: bool, token: str):
    """Extract conventions + docs from git history.

    Default: reads local git log + markdown files (zero network).
    Use --with-prs to also fetch PR review comments via API.
    If gh CLI is installed and authenticated, no --token needed.
    """
    from kronode.core.config import get_settings
    settings = get_settings()
    repo_path = settings.repo_path

    if not repo_path or not os.path.isdir(os.path.join(repo_path, ".git")):
        console.print("[red]No repo configured.[/red] Run `kronode init .` first.")
        raise SystemExit(1)

    # Resolve token: explicit --token > config > gh CLI
    resolved_token = token or settings.repo_token
    if with_prs and not resolved_token:
        gh_token = _get_gh_token()
        if gh_token:
            resolved_token = gh_token
            console.print("  [dim]Using gh CLI authentication[/dim]")
        else:
            console.print("[yellow]No token found.[/yellow] Either:")
            console.print("  1. Install and authenticate gh CLI: [cyan]gh auth login[/cyan]")
            console.print("  2. Pass a PAT: [cyan]kronode ingest --with-prs --token ghp_xxx[/cyan]")
            console.print("  Continuing without PR data...\n")
            with_prs = False

    console.print(f"\n[bold]Kronode ingest[/bold] — {repo_path}\n")

    asyncio.run(_ingest(repo_path, settings, with_prs, resolved_token))


async def _ingest(repo_path: str, settings, with_prs: bool, token: str):
    from kronode.core.database import init_db, AsyncSessionLocal
    from kronode.models.convention import Convention
    from kronode.models.doc_chunk import DocChunk
    from kronode.core.embeddings import get_embeddings_batch
    from sqlalchemy import select

    await init_db()

    org_id = settings.org_id
    total_conventions = 0
    total_docs = 0

    # 1. Local git conventions
    with console.status("[bold]Extracting conventions from git history..."):
        local_convs = _extract_local_conventions(repo_path)
        console.print(f"  [green]✓[/green] {len(local_convs)} conventions from git history")

    # 2. PR-based conventions (optional)
    pr_convs = []
    if with_prs and token:
        with console.status("[bold]Fetching PR review comments..."):
            try:
                from kronode.services.git_providers import get_git_provider
                git = get_git_provider(settings.repo_provider)
                # Get remote URL
                remote = subprocess.run(
                    ["git", "-C", repo_path, "remote", "get-url", "origin"],
                    capture_output=True, text=True,
                ).stdout.strip()

                prs = await git.fetch_merged_prs(remote, token, count=200)
                console.print(f"  [green]✓[/green] Fetched {len(prs)} merged PRs")

                # Extract from reviewer comments (no LLM)
                from kronode.services.convention_extractor import extract_reviewer_knowledge
                for pr in prs:
                    pr_convs.extend(extract_reviewer_knowledge(pr))

                # BYOK: also run LLM extraction
                if settings.mode == "byok":
                    from kronode.services.convention_extractor import extract_conventions_from_pr
                    for pr in prs:
                        llm_convs = await extract_conventions_from_pr(pr)
                        for c in llm_convs:
                            c["source_prs"] = [pr.get("url", "")]
                            c["frequency"] = 1
                        pr_convs.extend(llm_convs)

                console.print(f"  [green]✓[/green] {len(pr_convs)} conventions from PR reviews")
            except Exception as e:
                console.print(f"  [yellow]⚠[/yellow] PR fetch failed: {e}")

    # 3. Store conventions
    all_convs = local_convs + pr_convs
    if all_convs:
        async with AsyncSessionLocal() as db:
            for c in all_convs:
                db.add(Convention(
                    org_id=org_id,
                    rule=c["rule"],
                    category=c.get("category", "architecture"),
                    frequency=c.get("frequency", 1),
                    confidence=c.get("confidence", 0.5),
                    source_prs=c.get("source_prs", []),
                    source_files=c.get("source_files", []),
                    enforced_by=c.get("enforced_by", []),
                    layer="local",
                ))
            await db.commit()
        total_conventions = len(all_convs)

    # 4. Ingest markdown docs
    with console.status("[bold]Ingesting markdown documentation..."):
        docs = _extract_markdown_docs(repo_path)
        if docs:
            # Chunk and embed
            chunks = []
            for doc in docs:
                # Simple heading-based chunking
                content = doc["content"]
                sections = re.split(r'\n#{1,3}\s+', content)
                headings = re.findall(r'\n(#{1,3}\s+.+)', content)
                headings = [doc["path"]] + [h.strip("# ").strip() for h in headings]

                for i, section in enumerate(sections):
                    section = section.strip()
                    if len(section) < 30:
                        continue
                    heading = headings[min(i, len(headings) - 1)]
                    chunks.append({
                        "heading": f"{doc['path']} > {heading}",
                        "content": section[:3000],
                        "source_ref": doc["path"],
                    })

            # Embed
            texts = [c["content"][:500] for c in chunks]
            embeddings = await get_embeddings_batch(texts)

            async with AsyncSessionLocal() as db:
                for chunk, emb in zip(chunks, embeddings):
                    db.add(DocChunk(
                        org_id=org_id,
                        source_type="git",
                        source_ref=chunk["source_ref"],
                        heading=chunk["heading"],
                        content=chunk["content"],
                        embedding=emb,
                    ))
                await db.commit()
            total_docs = len(chunks)

        console.print(f"  [green]✓[/green] {len(docs)} files → {total_docs} doc chunks")

    # Summary
    console.print(f"\n[bold green]Done![/bold green]")
    console.print(f"  Conventions: {total_conventions}")
    console.print(f"  Doc chunks: {total_docs}")
    console.print(f"\nNext: [cyan]kronode serve[/cyan] to start the MCP server")
    console.print()
