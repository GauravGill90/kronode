from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.models.convention import Convention

router = APIRouter()


async def _get_org_id(user_data: dict, db: AsyncSession) -> int:
    result = await db.execute(select(User).where(User.clerk_id == user_data["user_id"]))
    user = result.scalar_one_or_none()
    if not user or not user.org_id:
        raise HTTPException(status_code=400, detail="Onboarding not complete")
    return user.org_id


@router.get("/conventions")
async def list_conventions(
    category: str | None = Query(None),
    layer: str | None = Query(None),
    include_suppressed: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    user_data: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org_id = await _get_org_id(user_data, db)

    query = select(Convention).where(
        (Convention.org_id == org_id) | (Convention.org_id.is_(None))  # include base conventions
    )

    if not include_suppressed:
        query = query.where(Convention.suppressed == False)  # noqa: E712
    if category:
        query = query.where(Convention.category == category)
    if layer:
        query = query.where(Convention.layer == layer)

    query = query.order_by(Convention.confidence.desc())

    # Count total
    from sqlalchemy import func
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Paginate
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    conventions = result.scalars().all()

    return {
        "conventions": [
            {
                "id": c.id,
                "rule": c.rule,
                "category": c.category,
                "examples": c.examples or [],
                "frequency": c.frequency,
                "confidence": c.confidence,
                "layer": c.layer,
                "source_prs": c.source_prs or [],
                "suppressed": c.suppressed,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in conventions
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.put("/conventions/{convention_id}")
async def update_convention(
    convention_id: int,
    body: dict,
    user_data: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Edit a convention's rule or category."""
    org_id = await _get_org_id(user_data, db)

    result = await db.execute(
        select(Convention).where(Convention.id == convention_id, Convention.org_id == org_id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Convention not found")

    if "rule" in body:
        conv.rule = body["rule"]
    if "category" in body:
        conv.category = body["category"]
    if "examples" in body:
        conv.examples = body["examples"]

    await db.commit()
    return {"ok": True}


@router.delete("/conventions/{convention_id}")
async def suppress_convention(
    convention_id: int,
    user_data: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Suppress a convention — it will never be injected again."""
    org_id = await _get_org_id(user_data, db)

    result = await db.execute(
        select(Convention).where(Convention.id == convention_id, Convention.org_id == org_id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Convention not found")

    conv.suppressed = True
    await db.commit()
    return {"ok": True}


@router.post("/conventions/extract", status_code=status.HTTP_202_ACCEPTED)
async def trigger_extraction(
    user_data: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger a convention extraction run for this org."""
    org_id = await _get_org_id(user_data, db)

    from app.pipeline.task_queue import run_convention_extraction
    run_convention_extraction.delay(org_id)
    return {"ok": True, "message": "Convention extraction queued."}


@router.post("/conventions/extract-base", status_code=status.HTTP_202_ACCEPTED)
async def trigger_base_extraction(
    user_data: dict = Depends(get_current_user),
):
    """Trigger base convention extraction from Cal.com (TypeScript base layer)."""
    from app.pipeline.task_queue import run_base_convention_extraction
    run_base_convention_extraction.delay()
    return {"ok": True, "message": "Base convention extraction from Cal.com queued."}
