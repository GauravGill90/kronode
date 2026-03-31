"""Google Drive doc provider — fetches Google Docs from a Drive folder.

Auth: Service account JSON key or OAuth token.
Fetches documents as plain text, chunks by heading.
"""
import hashlib
import logging

import httpx

from app.services.doc_providers.base import DocProvider, RawDoc, ChunkData

logger = logging.getLogger(__name__)


class GoogleDriveDocProvider(DocProvider):

    def _headers(self, token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}

    async def fetch(
        self,
        repo_url: str,  # Used as folder_id or "folder:<id>"
        token: str,
        existing_shas: dict[str, str] | None = None,
    ) -> list[RawDoc]:
        existing_shas = existing_shas or {}
        docs: list[RawDoc] = []
        headers = self._headers(token)

        # Parse folder ID
        folder_id = repo_url
        if folder_id.startswith("folder:"):
            folder_id = folder_id[7:]
        # Handle full Drive URLs
        if "drive.google.com" in folder_id:
            # Extract folder ID from URL
            parts = folder_id.rstrip("/").split("/")
            folder_id = parts[-1]

        async with httpx.AsyncClient(timeout=30) as client:
            # List Google Docs in folder
            query = f"'{folder_id}' in parents and mimeType='application/vnd.google-apps.document' and trashed=false"
            resp = await client.get(
                "https://www.googleapis.com/drive/v3/files",
                headers=headers,
                params={
                    "q": query,
                    "fields": "files(id,name,modifiedTime)",
                    "pageSize": 100,
                },
            )

            if resp.status_code != 200:
                logger.error(f"[GDrive] List files failed: {resp.status_code} {resp.text[:200]}")
                return []

            files = resp.json().get("files", [])

            for file in files:
                file_id = file["id"]
                modified = file.get("modifiedTime", "")
                content_sha = hashlib.sha256(modified.encode()).hexdigest()[:16]

                # Delta sync
                if existing_shas.get(file_id) == content_sha:
                    continue

                # Export as plain text
                export_resp = await client.get(
                    f"https://www.googleapis.com/drive/v3/files/{file_id}/export",
                    headers=headers,
                    params={"mimeType": "text/plain"},
                )

                if export_resp.status_code != 200:
                    logger.warning(f"[GDrive] Export failed for {file['name']}: {export_resp.status_code}")
                    continue

                content = export_resp.text
                if not content.strip():
                    continue

                docs.append(RawDoc(
                    source_ref=file_id,
                    source_url=f"https://docs.google.com/document/d/{file_id}",
                    file_sha=content_sha,
                    content=content,
                    metadata={"title": file["name"], "modified": modified},
                ))

        logger.info(f"[GDrive] Fetched {len(docs)} changed/new docs from folder")
        return docs

    def chunk(self, raw_doc: RawDoc) -> list[ChunkData]:
        """Split a Google Doc into heading-level chunks.

        Google Docs exported as plain text don't have markdown headings,
        but they do have lines that are all-caps or short standalone lines
        that likely represent section headers.
        """
        title = raw_doc.metadata.get("title", "Untitled")
        content = raw_doc.content
        lines = content.split("\n")
        chunks: list[ChunkData] = []

        current_heading = title
        current_lines: list[str] = []

        for line in lines:
            stripped = line.strip()
            # Heuristic: short lines (< 80 chars) that end without punctuation are likely headings
            is_heading = (
                stripped
                and len(stripped) < 80
                and not stripped.endswith((".", ",", ";", ":", "?", "!"))
                and stripped == stripped.title()  # Title Case
                and len(current_lines) > 2  # Not the first few lines
            )

            if is_heading:
                if current_lines:
                    chunk_content = "\n".join(current_lines).strip()
                    if chunk_content:
                        chunks.append(ChunkData(
                            heading=f"{title} > {current_heading}",
                            content=chunk_content,
                            metadata={"file_id": raw_doc.source_ref},
                        ))
                current_heading = stripped
                current_lines = []
            else:
                current_lines.append(line)

        # Final chunk
        if current_lines:
            chunk_content = "\n".join(current_lines).strip()
            if chunk_content:
                chunks.append(ChunkData(
                    heading=f"{title} > {current_heading}" if current_heading != title else title,
                    content=chunk_content,
                    metadata={"file_id": raw_doc.source_ref},
                ))

        if not chunks and content.strip():
            chunks.append(ChunkData(
                heading=title,
                content=content[:3000],
                metadata={"file_id": raw_doc.source_ref},
            ))

        return chunks
