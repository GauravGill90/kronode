"""Bitbucket document provider.

Fetches markdown files from a Bitbucket Cloud repo and chunks them by heading.
Mirrors git_provider.py but uses the Bitbucket Cloud REST API v2.
"""
import logging
import re

import httpx

from app.services.doc_providers.base import DocProvider, RawDoc, ChunkData
from app.services.bitbucket_service import (
    BITBUCKET_API,
    _auth_headers,
    _list_all_files,
    _parse_repo,
)

logger = logging.getLogger(__name__)

# File patterns to ingest
_DOC_EXTENSIONS = {".md", ".mdx"}

# Directories to skip entirely
_SKIP_DIRS = {
    "node_modules", ".git", "dist", "build", ".next", "__pycache__",
    ".venv", "venv", "coverage", ".turbo", ".changeset",
}

# Max raw doc size (bytes) — skip huge generated files
_MAX_FILE_SIZE = 50_000  # 50 KB

# Max chunk size (bytes)
_MAX_CHUNK_SIZE = 2048

# Minimum meaningful content after stripping links/images
_MIN_CONTENT_LENGTH = 50


class BitbucketDocProvider(DocProvider):

    async def fetch(
        self,
        repo_url: str,
        token: str,
        existing_shas: dict[str, str] | None = None,
    ) -> list[RawDoc]:
        existing_shas = existing_shas or {}
        workspace, repo_slug = _parse_repo(repo_url)
        headers = _auth_headers(token)

        async with httpx.AsyncClient(timeout=30) as client:
            # Get default branch
            resp = await client.get(
                f"{BITBUCKET_API}/repositories/{workspace}/{repo_slug}",
                headers=headers,
            )
            resp.raise_for_status()
            default_branch = resp.json()["mainbranch"]["name"]

            # Resolve branch → commit hash (for stable src URLs)
            resp = await client.get(
                f"{BITBUCKET_API}/repositories/{workspace}/{repo_slug}/refs/branches/{default_branch}",
                headers=headers,
            )
            resp.raise_for_status()
            commit = resp.json()["target"]["hash"]

            # Get full recursive file listing
            all_files = await _list_all_files(
                client, workspace, repo_slug, commit, token
            )

        # Filter to markdown files, skip unwanted dirs and large files
        doc_items = []
        for item in all_files:
            path = item.get("path", "")
            if not any(path.endswith(ext) for ext in _DOC_EXTENSIONS):
                continue
            parts = path.split("/")
            if any(p in _SKIP_DIRS for p in parts[:-1]):
                continue
            if item.get("size", 0) > _MAX_FILE_SIZE:
                continue
            doc_items.append(item)

        logger.info(
            f"[BitbucketDocProvider] {workspace}/{repo_slug}: "
            f"{len(doc_items)} markdown files found"
        )

        # Delta sync — only fetch changed/new files
        # Bitbucket uses the file's commit hash as the SHA equivalent
        to_fetch = []
        for item in doc_items:
            source_ref = f"{workspace}/{repo_slug}:{item['path']}"
            file_sha = item.get("commit", {}).get("hash", item.get("path"))
            if existing_shas.get(source_ref) == file_sha:
                continue  # unchanged
            to_fetch.append((item, file_sha))

        logger.info(
            f"[BitbucketDocProvider] {len(to_fetch)} files changed/new "
            f"(skipped {len(doc_items) - len(to_fetch)} unchanged)"
        )

        raw_docs: list[RawDoc] = []
        async with httpx.AsyncClient(timeout=20) as client:
            for item, file_sha in to_fetch:
                path = item["path"]
                try:
                    resp = await client.get(
                        f"{BITBUCKET_API}/repositories/{workspace}/{repo_slug}/src/{commit}/{path}",
                        headers=headers,
                    )
                    if resp.status_code != 200:
                        continue
                    content = resp.text

                    raw_docs.append(RawDoc(
                        source_ref=f"{workspace}/{repo_slug}:{path}",
                        source_url=(
                            f"https://bitbucket.org/{workspace}/{repo_slug}"
                            f"/src/{default_branch}/{path}"
                        ),
                        file_sha=file_sha,
                        content=content,
                        metadata={"path": path, "size": item.get("size", 0)},
                    ))
                except Exception as exc:
                    logger.warning(f"[BitbucketDocProvider] Failed to fetch {path}: {exc}")

        logger.info(f"[BitbucketDocProvider] Fetched {len(raw_docs)} doc files")
        return raw_docs

    def chunk(self, raw_doc: RawDoc) -> list[ChunkData]:
        file_path = raw_doc.metadata.get("path", raw_doc.source_ref)
        content = raw_doc.content
        chunks: list[ChunkData] = []

        # Split by headings (# / ## / ###)
        sections = re.split(r'^(#{1,3}\s+.+)$', content, flags=re.MULTILINE)

        current_heading = file_path
        current_body = ""

        for section in sections:
            if re.match(r'^#{1,3}\s+', section):
                if current_body.strip():
                    chunks.extend(self._make_chunks(file_path, current_heading, current_body))
                level_match = re.match(r'^(#{1,3})\s+(.+)', section)
                level = len(level_match.group(1)) if level_match else 2
                heading_text = level_match.group(2).strip() if level_match else section.strip()
                current_heading = f"{file_path} > {'#' * level} {heading_text}"
                current_body = ""
            else:
                current_body += section

        if current_body.strip():
            chunks.extend(self._make_chunks(file_path, current_heading, current_body))

        return chunks

    def _make_chunks(self, file_path: str, heading: str, body: str) -> list[ChunkData]:
        body = body.strip()
        if not body:
            return []

        stripped = re.sub(r'!?\[.*?\]\(.*?\)', '', body)
        stripped = re.sub(r'<.*?>', '', stripped).strip()
        if len(stripped) < _MIN_CONTENT_LENGTH:
            return []

        if len(body.encode("utf-8")) <= _MAX_CHUNK_SIZE:
            return [ChunkData(
                heading=heading,
                content=body,
                metadata={"file_path": file_path},
            )]

        paragraphs = re.split(r'\n\n+', body)
        chunks: list[ChunkData] = []
        current = ""
        for para in paragraphs:
            candidate = (current + "\n\n" + para).strip()
            if len(candidate.encode("utf-8")) > _MAX_CHUNK_SIZE and current:
                chunks.append(ChunkData(
                    heading=heading,
                    content=current.strip(),
                    metadata={"file_path": file_path},
                ))
                current = para
            else:
                current = candidate
        if current.strip():
            chunks.append(ChunkData(
                heading=heading,
                content=current.strip(),
                metadata={"file_path": file_path},
            ))

        return chunks
