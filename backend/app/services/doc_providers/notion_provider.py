"""Notion doc provider — fetches pages from a Notion workspace via API.

Auth: Integration token (internal integration).
Config: NOTION_TOKEN env var or per-org token in onboarding config.
"""
import hashlib
import logging

import httpx

from app.services.doc_providers.base import DocProvider, RawDoc, ChunkData

logger = logging.getLogger(__name__)

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


class NotionDocProvider(DocProvider):

    def _headers(self, token: str) -> dict:
        return {
            "Authorization": f"Bearer {token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        }

    async def fetch(
        self,
        repo_url: str,  # Not used — Notion uses workspace-wide search
        token: str,
        existing_shas: dict[str, str] | None = None,
    ) -> list[RawDoc]:
        existing_shas = existing_shas or {}
        docs: list[RawDoc] = []
        headers = self._headers(token)

        async with httpx.AsyncClient(timeout=30) as client:
            # Search all pages in the workspace
            has_more = True
            start_cursor = None

            while has_more:
                body: dict = {"filter": {"property": "object", "value": "page"}, "page_size": 100}
                if start_cursor:
                    body["start_cursor"] = start_cursor

                resp = await client.post(f"{NOTION_API}/search", headers=headers, json=body)
                if resp.status_code != 200:
                    logger.error(f"[Notion] Search failed: {resp.status_code} {resp.text[:200]}")
                    break

                data = resp.json()
                has_more = data.get("has_more", False)
                start_cursor = data.get("next_cursor")

                for page in data.get("results", []):
                    page_id = page["id"]
                    last_edited = page.get("last_edited_time", "")
                    content_sha = hashlib.sha256(last_edited.encode()).hexdigest()[:16]

                    # Delta sync
                    if existing_shas.get(page_id) == content_sha:
                        continue

                    # Get page title
                    title = ""
                    props = page.get("properties", {})
                    for prop in props.values():
                        if prop.get("type") == "title":
                            title_parts = prop.get("title", [])
                            title = "".join(t.get("plain_text", "") for t in title_parts)
                            break

                    if not title:
                        title = "Untitled"

                    # Fetch page blocks (content)
                    content = await self._fetch_blocks(client, headers, page_id)
                    if not content.strip():
                        continue

                    page_url = page.get("url", f"https://notion.so/{page_id.replace('-', '')}")

                    docs.append(RawDoc(
                        source_ref=page_id,
                        source_url=page_url,
                        file_sha=content_sha,
                        content=content,
                        metadata={"title": title, "last_edited": last_edited},
                    ))

        logger.info(f"[Notion] Fetched {len(docs)} changed/new pages")
        return docs

    async def _fetch_blocks(self, client: httpx.AsyncClient, headers: dict, block_id: str, depth: int = 0) -> str:
        """Recursively fetch all blocks for a page."""
        if depth > 3:
            return ""

        parts: list[str] = []
        has_more = True
        start_cursor = None

        while has_more:
            params: dict = {"page_size": 100}
            if start_cursor:
                params["start_cursor"] = start_cursor

            resp = await client.get(
                f"{NOTION_API}/blocks/{block_id}/children",
                headers=headers,
                params=params,
            )
            if resp.status_code != 200:
                break

            data = resp.json()
            has_more = data.get("has_more", False)
            start_cursor = data.get("next_cursor")

            for block in data.get("results", []):
                text = self._extract_text(block)
                if text:
                    parts.append(text)

                # Recurse into children
                if block.get("has_children"):
                    child_text = await self._fetch_blocks(client, headers, block["id"], depth + 1)
                    if child_text:
                        parts.append(child_text)

        return "\n".join(parts)

    def _extract_text(self, block: dict) -> str:
        """Extract plain text from a Notion block."""
        block_type = block.get("type", "")
        block_data = block.get(block_type, {})

        # Handle rich text blocks
        if "rich_text" in block_data:
            text = "".join(rt.get("plain_text", "") for rt in block_data["rich_text"])
            if block_type.startswith("heading"):
                level = block_type[-1]  # heading_1, heading_2, heading_3
                return f"{'#' * int(level)} {text}"
            return text

        # Handle special block types
        if block_type == "code":
            lang = block_data.get("language", "")
            code_text = "".join(rt.get("plain_text", "") for rt in block_data.get("rich_text", []))
            return f"```{lang}\n{code_text}\n```"

        if block_type == "to_do":
            checked = "x" if block_data.get("checked") else " "
            text = "".join(rt.get("plain_text", "") for rt in block_data.get("rich_text", []))
            return f"- [{checked}] {text}"

        if block_type in ("bulleted_list_item", "numbered_list_item"):
            text = "".join(rt.get("plain_text", "") for rt in block_data.get("rich_text", []))
            return f"- {text}"

        if block_type == "divider":
            return "---"

        return ""

    def chunk(self, raw_doc: RawDoc) -> list[ChunkData]:
        """Split a Notion page into heading-level chunks."""
        title = raw_doc.metadata.get("title", "Untitled")
        content = raw_doc.content
        lines = content.split("\n")
        chunks: list[ChunkData] = []

        current_heading = title
        current_lines: list[str] = []

        for line in lines:
            if line.startswith("#"):
                # Save previous chunk
                if current_lines:
                    chunk_content = "\n".join(current_lines).strip()
                    if chunk_content:
                        chunks.append(ChunkData(
                            heading=f"{title} > {current_heading}",
                            content=chunk_content,
                            metadata={"page_id": raw_doc.source_ref},
                        ))
                current_heading = line.lstrip("#").strip()
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
                    metadata={"page_id": raw_doc.source_ref},
                ))

        if not chunks and content.strip():
            chunks.append(ChunkData(
                heading=title,
                content=content[:3000],
                metadata={"page_id": raw_doc.source_ref},
            ))

        return chunks
