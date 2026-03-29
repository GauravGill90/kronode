"""Git (GitHub) document provider.

Fetches markdown files from a GitHub repo and chunks them by heading.
"""
import logging
import re

import httpx

from app.services.doc_providers.base import DocProvider, RawDoc, ChunkData

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"

# File patterns to ingest
_DOC_EXTENSIONS = {".md", ".mdx"}

# Directories to skip entirely
_SKIP_DIRS = {
    "node_modules", ".git", "dist", "build", ".next", "__pycache__",
    ".venv", "venv", "coverage", ".turbo", ".changeset",
}

# Max raw doc size to fetch (skip huge generated files)
_MAX_FILE_SIZE = 50_000  # 50KB

# Max chunk size
_MAX_CHUNK_SIZE = 2048

# Minimum meaningful content after stripping links/images
_MIN_CONTENT_LENGTH = 50


class GitDocProvider(DocProvider):

    async def fetch(
        self,
        repo_url: str,
        token: str,
        existing_shas: dict[str, str] | None = None,
    ) -> list[RawDoc]:
        existing_shas = existing_shas or {}
        owner, repo = _parse_repo(repo_url)
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        async with httpx.AsyncClient(timeout=30) as client:
            # Get default branch
            resp = await client.get(f"{GITHUB_API}/repos/{owner}/{repo}", headers=headers)
            resp.raise_for_status()
            default_branch = resp.json()["default_branch"]

            # Get full recursive tree (includes SHAs)
            resp = await client.get(
                f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/{default_branch}?recursive=1",
                headers=headers,
            )
            resp.raise_for_status()
            tree = resp.json().get("tree", [])

        # Filter to markdown files, skip unwanted dirs
        doc_items = []
        for item in tree:
            if item["type"] != "blob":
                continue
            path = item["path"]
            if not any(path.endswith(ext) for ext in _DOC_EXTENSIONS):
                continue
            parts = path.split("/")
            if any(p in _SKIP_DIRS for p in parts[:-1]):
                continue
            # Skip very large files (size is in the tree response)
            if item.get("size", 0) > _MAX_FILE_SIZE:
                continue
            doc_items.append(item)

        logger.info(f"[GitDocProvider] {owner}/{repo}: {len(doc_items)} markdown files found in tree")

        # Delta sync — only fetch changed/new files
        to_fetch = []
        for item in doc_items:
            source_ref = f"{owner}/{repo}:{item['path']}"
            if existing_shas.get(source_ref) == item["sha"]:
                continue  # unchanged
            to_fetch.append(item)

        logger.info(f"[GitDocProvider] {len(to_fetch)} files changed/new (skipped {len(doc_items) - len(to_fetch)} unchanged)")

        # Fetch file contents
        raw_docs = []
        async with httpx.AsyncClient(timeout=20) as client:
            for item in to_fetch:
                try:
                    resp = await client.get(
                        f"{GITHUB_API}/repos/{owner}/{repo}/contents/{item['path']}",
                        headers=headers,
                    )
                    if resp.status_code != 200:
                        continue
                    data = resp.json()
                    if data.get("encoding") != "base64" or not data.get("content"):
                        continue

                    import base64
                    content = base64.b64decode(data["content"]).decode("utf-8", errors="replace")

                    raw_docs.append(RawDoc(
                        source_ref=f"{owner}/{repo}:{item['path']}",
                        source_url=f"https://github.com/{owner}/{repo}/blob/{default_branch}/{item['path']}",
                        file_sha=item["sha"],
                        content=content,
                        metadata={"path": item["path"], "size": item.get("size", 0)},
                    ))
                except Exception as exc:
                    logger.warning(f"[GitDocProvider] Failed to fetch {item['path']}: {exc}")

        logger.info(f"[GitDocProvider] Fetched {len(raw_docs)} doc files")
        return raw_docs

    def chunk(self, raw_doc: RawDoc) -> list[ChunkData]:
        file_path = raw_doc.metadata.get("path", raw_doc.source_ref)
        content = raw_doc.content
        chunks: list[ChunkData] = []

        # Split by headings (# or ##)
        sections = re.split(r'^(#{1,3}\s+.+)$', content, flags=re.MULTILINE)

        # sections alternates: [preamble, heading1, body1, heading2, body2, ...]
        current_heading = file_path  # preamble gets the filename as heading
        current_body = ""

        for i, section in enumerate(sections):
            if re.match(r'^#{1,3}\s+', section):
                # Save previous section
                if current_body.strip():
                    chunks.extend(self._make_chunks(file_path, current_heading, current_body))
                # Extract heading level
                level_match = re.match(r'^(#{1,3})\s+(.+)', section)
                level = len(level_match.group(1)) if level_match else 2
                heading_text = level_match.group(2).strip() if level_match else section.strip()
                current_heading = f"{file_path} > {'#' * level} {heading_text}"
                current_body = ""
            else:
                current_body += section

        # Don't forget the last section
        if current_body.strip():
            chunks.extend(self._make_chunks(file_path, current_heading, current_body))

        return chunks

    def _make_chunks(self, file_path: str, heading: str, body: str) -> list[ChunkData]:
        """Create chunks from a section body, splitting if too large."""
        body = body.strip()
        if not body:
            return []

        # Check if content is meaningful (not just links/images)
        stripped = re.sub(r'!?\[.*?\]\(.*?\)', '', body)
        stripped = re.sub(r'<.*?>', '', stripped)
        stripped = stripped.strip()
        if len(stripped) < _MIN_CONTENT_LENGTH:
            return []

        # If body fits in one chunk, return it
        if len(body.encode("utf-8")) <= _MAX_CHUNK_SIZE:
            return [ChunkData(
                heading=heading,
                content=body,
                metadata={"file_path": file_path},
            )]

        # Split at paragraph boundaries
        paragraphs = re.split(r'\n\n+', body)
        chunks = []
        current = ""
        for para in paragraphs:
            if len((current + "\n\n" + para).encode("utf-8")) > _MAX_CHUNK_SIZE and current:
                chunks.append(ChunkData(
                    heading=heading,
                    content=current.strip(),
                    metadata={"file_path": file_path},
                ))
                current = para
            else:
                current = (current + "\n\n" + para).strip()
        if current.strip():
            chunks.append(ChunkData(
                heading=heading,
                content=current.strip(),
                metadata={"file_path": file_path},
            ))

        return chunks


def _parse_repo(repo_url: str) -> tuple[str, str]:
    repo_url = repo_url.rstrip("/")
    if repo_url.endswith(".git"):
        repo_url = repo_url[:-4]
    parts = repo_url.split("/")
    return parts[-2], parts[-1]
