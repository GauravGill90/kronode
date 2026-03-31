"""Confluence Cloud document provider.

Fetches pages from a Confluence space, chunks them by heading.
Uses the Confluence REST API v2 with Atlassian API token auth.
"""
import base64
import hashlib
import logging
import re

import httpx

from app.services.doc_providers.base import DocProvider, RawDoc, ChunkData

logger = logging.getLogger(__name__)

_MAX_CHUNK_SIZE = 2048
_MIN_CONTENT_LENGTH = 50


def _auth_headers(email: str, api_token: str) -> dict[str, str]:
    """Atlassian Cloud uses Basic auth with email:api_token."""
    encoded = base64.b64encode(f"{email}:{api_token}".encode()).decode()
    return {
        "Authorization": f"Basic {encoded}",
        "Accept": "application/json",
    }


def _parse_confluence_url(url: str) -> tuple[str, str]:
    """Extract base_url and space_key from a Confluence space URL.

    Example: https://foo.atlassian.net/wiki/spaces/SIDC/overview
    Returns: ("https://foo.atlassian.net/wiki", "SIDC")
    """
    url = url.rstrip("/")
    # Match /wiki/spaces/{SPACE_KEY}
    match = re.search(r"(/wiki)/spaces/([^/]+)", url)
    if not match:
        raise ValueError(f"Cannot parse Confluence space URL: {url}")
    base = url[:url.index(match.group(0))] + match.group(1)
    space_key = match.group(2)
    return base, space_key


def _html_to_text(html: str) -> str:
    """Simple HTML → plain text conversion. Strips tags, keeps headings as markdown."""
    # Convert headings
    text = re.sub(r"<h([1-6])[^>]*>(.*?)</h\1>", lambda m: "#" * int(m.group(1)) + " " + m.group(2), html)
    # Convert lists
    text = re.sub(r"<li[^>]*>(.*?)</li>", r"- \1", text)
    # Convert line breaks and paragraphs
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"</p>", "\n\n", text)
    # Strip remaining tags
    text = re.sub(r"<[^>]+>", "", text)
    # Clean up whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Decode HTML entities
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&#39;", "'")
    return text.strip()


class ConfluenceDocProvider(DocProvider):

    async def fetch(
        self,
        repo_url: str,  # Confluence space URL
        token: str,      # email:api_token format
        existing_shas: dict[str, str] | None = None,
    ) -> list[RawDoc]:
        existing_shas = existing_shas or {}

        # Parse the token — expect email:api_token
        if ":" not in token:
            logger.warning("[Confluence] Token must be email:api_token format")
            return []
        email, api_token = token.split(":", 1)

        base_url, space_key = _parse_confluence_url(repo_url)
        headers = _auth_headers(email, api_token)

        raw_docs: list[RawDoc] = []

        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            # Fetch all pages in the space using v2 API
            url: str | None = f"{base_url}/api/v2/spaces"
            # First get the space ID
            resp = await client.get(
                f"{base_url}/api/v2/spaces",
                headers=headers,
                params={"keys": space_key},
            )
            if not resp.is_success:
                logger.warning(f"[Confluence] Failed to fetch space {space_key}: {resp.status_code}")
                return []

            spaces = resp.json().get("results", [])
            if not spaces:
                logger.warning(f"[Confluence] Space {space_key} not found")
                return []

            space_id = spaces[0]["id"]

            # Fetch pages in the space
            pages_url: str | None = f"{base_url}/api/v2/spaces/{space_id}/pages"
            all_pages = []

            while pages_url:
                resp = await client.get(
                    pages_url,
                    headers=headers,
                    params={"limit": 50, "body-format": "storage"},
                )
                if not resp.is_success:
                    logger.warning(f"[Confluence] Failed to fetch pages: {resp.status_code}")
                    break

                data = resp.json()
                all_pages.extend(data.get("results", []))
                # Pagination
                next_link = data.get("_links", {}).get("next")
                pages_url = f"{base_url}{next_link}" if next_link else None

            logger.info(f"[Confluence] Space {space_key}: {len(all_pages)} pages found")

            # Process each page
            for page in all_pages:
                page_id = page["id"]
                title = page.get("title", "Untitled")
                version = str(page.get("version", {}).get("number", "0"))
                source_ref = f"confluence:{space_key}:{page_id}"

                # Delta sync — skip unchanged pages
                content_sha = hashlib.sha256(f"{page_id}:{version}".encode()).hexdigest()[:16]
                if existing_shas.get(source_ref) == content_sha:
                    continue

                # Get page body — may need separate fetch if not included
                body = page.get("body", {}).get("storage", {}).get("value", "")
                if not body:
                    # Fetch individual page with body
                    page_resp = await client.get(
                        f"{base_url}/api/v2/pages/{page_id}",
                        headers=headers,
                        params={"body-format": "storage"},
                    )
                    if page_resp.is_success:
                        body = page_resp.json().get("body", {}).get("storage", {}).get("value", "")

                if not body:
                    continue

                # Convert HTML to plain text
                text = _html_to_text(body)
                if len(text) < _MIN_CONTENT_LENGTH:
                    continue

                page_url = page.get("_links", {}).get("webui", "")
                if page_url and not page_url.startswith("http"):
                    page_url = f"{base_url}{page_url}"

                raw_docs.append(RawDoc(
                    source_ref=source_ref,
                    source_url=page_url,
                    file_sha=content_sha,
                    content=text,
                    metadata={"title": title, "page_id": page_id, "space_key": space_key},
                ))

        logger.info(f"[Confluence] Fetched {len(raw_docs)} changed/new pages from {space_key}")
        return raw_docs

    def chunk(self, raw_doc: RawDoc) -> list[ChunkData]:
        title = raw_doc.metadata.get("title", raw_doc.source_ref)
        content = raw_doc.content
        chunks: list[ChunkData] = []

        # Split by headings
        sections = re.split(r"^(#{1,3}\s+.+)$", content, flags=re.MULTILINE)

        current_heading = title
        current_body = ""

        for section in sections:
            if re.match(r"^#{1,3}\s+", section):
                if current_body.strip():
                    chunks.extend(self._make_chunks(title, current_heading, current_body))
                heading_text = re.sub(r"^#{1,3}\s+", "", section).strip()
                current_heading = f"{title} > {heading_text}"
                current_body = ""
            else:
                current_body += section

        if current_body.strip():
            chunks.extend(self._make_chunks(title, current_heading, current_body))

        return chunks

    def _make_chunks(self, title: str, heading: str, body: str) -> list[ChunkData]:
        body = body.strip()
        if not body or len(body) < _MIN_CONTENT_LENGTH:
            return []

        if len(body.encode("utf-8")) <= _MAX_CHUNK_SIZE:
            return [ChunkData(heading=heading, content=body, metadata={"title": title})]

        # Split by paragraphs
        paragraphs = re.split(r"\n\n+", body)
        chunks: list[ChunkData] = []
        current = ""
        for para in paragraphs:
            candidate = (current + "\n\n" + para).strip()
            if len(candidate.encode("utf-8")) > _MAX_CHUNK_SIZE and current:
                chunks.append(ChunkData(heading=heading, content=current.strip(), metadata={"title": title}))
                current = para
            else:
                current = candidate
        if current.strip():
            chunks.append(ChunkData(heading=heading, content=current.strip(), metadata={"title": title}))
        return chunks
