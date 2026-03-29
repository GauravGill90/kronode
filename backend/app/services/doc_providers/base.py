"""Abstract base for document providers.

Each provider knows how to fetch raw documents from a source (GitHub, Confluence,
Google Drive, Notion, etc.) and chunk them into heading-level pieces.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class RawDoc:
    """A single document fetched from a source, before chunking."""
    source_ref: str        # unique id, e.g. "calcom/cal.com:docs/api.md"
    source_url: str        # full URL to view the doc
    file_sha: str          # content hash for delta sync
    content: str           # raw text content
    metadata: dict = field(default_factory=dict)  # provider-specific extras


@dataclass
class ChunkData:
    """A single chunk extracted from a raw document."""
    heading: str           # section heading, e.g. "docs/api.md > ## Authentication"
    content: str           # chunk body text
    metadata: dict = field(default_factory=dict)  # heading_level, file_path, etc.


class DocProvider(ABC):
    """Interface for document source providers."""

    @abstractmethod
    async def fetch(
        self,
        repo_url: str,
        token: str,
        existing_shas: dict[str, str] | None = None,
    ) -> list[RawDoc]:
        """Fetch raw documents from the source.

        Args:
            repo_url: Repository URL or source identifier.
            token: Auth token for the source.
            existing_shas: Map of source_ref → file_sha for delta sync.
                           Only return docs where SHA differs or is new.

        Returns:
            List of RawDoc objects for changed/new documents.
        """
        ...

    @abstractmethod
    def chunk(self, raw_doc: RawDoc) -> list[ChunkData]:
        """Split a raw document into heading-level chunks.

        Returns:
            List of ChunkData, each representing a coherent section.
        """
        ...
