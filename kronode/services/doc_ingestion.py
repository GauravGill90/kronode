"""Document ingestion service.

Orchestrates: provider.fetch() → chunk → embed → store.
Agnostic to source type — delegates to registered DocProviders.
"""
import logging

from sqlalchemy import select, delete

from kronode.core.database import AsyncSessionLocal
from kronode.core.embeddings import get_embeddings_batch, cosine_similarity, get_embedding
from kronode.models.doc_chunk import DocChunk
from kronode.services.doc_providers import get_provider

logger = logging.getLogger(__name__)


async def ingest_docs(org_id: int, source_type: str = "git") -> int:
    """Run document ingestion for an org. Returns number of chunks stored."""

    # Load org config
    from kronode.models.org import OnboardingConfig
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(OnboardingConfig).where(OnboardingConfig.org_id == org_id)
        )
        config = result.scalar_one_or_none()

    if not config or not config.repo_url or not config.github_access_token:
        logger.warning(f"[DocIngestion] Org {org_id}: no repo or token — skipping")
        return 0

    provider = get_provider(source_type)

    # Load existing SHAs for delta sync
    async with AsyncSessionLocal() as db:
        existing_rows = (await db.execute(
            select(DocChunk.source_ref, DocChunk.file_sha)
            .where(DocChunk.org_id == org_id, DocChunk.source_type == source_type)
        )).all()
    existing_shas = {ref: sha for ref, sha in existing_rows}

    logger.info(f"[DocIngestion] Org {org_id}, source={source_type}: {len(existing_shas)} existing docs in DB")

    # Fetch changed/new documents
    raw_docs = await provider.fetch(
        repo_url=config.repo_url,
        token=config.github_access_token,
        existing_shas=existing_shas,
    )

    if not raw_docs:
        logger.info(f"[DocIngestion] Org {org_id}: no new/changed docs — up to date")
        return 0

    logger.info(f"[DocIngestion] Org {org_id}: {len(raw_docs)} docs to process")

    # Chunk all documents
    all_chunks = []
    for raw_doc in raw_docs:
        chunks = provider.chunk(raw_doc)
        for chunk in chunks:
            all_chunks.append({
                "source_ref": raw_doc.source_ref,
                "source_url": raw_doc.source_url,
                "file_sha": raw_doc.file_sha,
                "heading": chunk.heading,
                "content": chunk.content,
                "metadata": {**raw_doc.metadata, **chunk.metadata},
            })

    logger.info(f"[DocIngestion] Org {org_id}: {len(raw_docs)} docs → {len(all_chunks)} chunks")

    if not all_chunks:
        return 0

    # Generate embeddings in batch
    texts = [c["content"] for c in all_chunks]
    embeddings = await get_embeddings_batch(texts)
    for i, emb in enumerate(embeddings):
        all_chunks[i]["embedding"] = emb

    # Upsert: delete old chunks for changed files, insert new ones
    changed_refs = {c["source_ref"] for c in all_chunks}
    stored = 0

    async with AsyncSessionLocal() as db:
        # Delete old chunks for files that changed
        if changed_refs:
            await db.execute(
                delete(DocChunk).where(
                    DocChunk.org_id == org_id,
                    DocChunk.source_type == source_type,
                    DocChunk.source_ref.in_(changed_refs),
                )
            )

        # Insert new chunks
        for c in all_chunks:
            db.add(DocChunk(
                org_id=org_id,
                source_type=source_type,
                source_ref=c["source_ref"],
                source_url=c["source_url"],
                file_sha=c["file_sha"],
                heading=c["heading"],
                content=c["content"],
                embedding=c["embedding"],
                extra=c["metadata"],
            ))
            stored += 1

        # Clean up docs that no longer exist in the source
        if existing_shas:
            fetched_refs = {d.source_ref for d in raw_docs}
            all_known_refs = set(existing_shas.keys())
            # We can't know which refs were deleted without a full tree listing.
            # The provider already fetched the full tree, so refs not in the tree are stale.
            # For now, we only delete changed refs above. Full cleanup requires the provider
            # to also return a list of all valid refs — can add later.

        await db.commit()

    logger.info(f"[DocIngestion] Org {org_id}: stored {stored} chunks from {len(raw_docs)} docs")
    return stored


async def query_relevant_chunks(
    org_id: int,
    description: str,
    source_type: str | None = None,
    max_chunks: int = 5,
) -> list[dict]:
    """Find the most relevant doc chunks for a task description.

    Returns list of dicts with: heading, content, source_url, similarity.
    """
    task_embedding = await get_embedding(description)
    if not task_embedding:
        # No embedding available — fall back to keyword match
        return await _keyword_fallback(org_id, description, source_type, max_chunks)

    # Load all chunks with embeddings for this org
    async with AsyncSessionLocal() as db:
        query = (
            select(DocChunk)
            .where(
                DocChunk.org_id == org_id,
                DocChunk.embedding.isnot(None),
            )
        )
        if source_type:
            query = query.where(DocChunk.source_type == source_type)
        rows = (await db.execute(query)).scalars().all()

    if not rows:
        return []

    # Rank by cosine similarity
    scored = []
    for chunk in rows:
        sim = cosine_similarity(task_embedding, chunk.embedding)
        if sim > 0.25:  # threshold to avoid noise
            scored.append((sim, chunk))

    scored.sort(key=lambda x: -x[0])

    return [
        {
            "heading": chunk.heading,
            "content": chunk.content[:2000],
            "source_url": chunk.source_url,
            "similarity": round(sim, 3),
        }
        for sim, chunk in scored[:max_chunks]
    ]


async def _keyword_fallback(
    org_id: int,
    description: str,
    source_type: str | None,
    max_chunks: int,
) -> list[dict]:
    """Simple keyword overlap fallback when embeddings are unavailable."""
    words = set(description.lower().split())
    if not words:
        return []

    async with AsyncSessionLocal() as db:
        query = select(DocChunk).where(DocChunk.org_id == org_id)
        if source_type:
            query = query.where(DocChunk.source_type == source_type)
        rows = (await db.execute(query)).scalars().all()

    scored = []
    for chunk in rows:
        chunk_words = set(chunk.content.lower().split())
        overlap = len(words & chunk_words)
        if overlap > 0:
            scored.append((overlap, chunk))

    scored.sort(key=lambda x: -x[0])

    return [
        {
            "heading": chunk.heading,
            "content": chunk.content[:2000],
            "source_url": chunk.source_url,
            "similarity": 0.0,
        }
        for _, chunk in scored[:max_chunks]
    ]
