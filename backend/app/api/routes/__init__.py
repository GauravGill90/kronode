from fastapi import APIRouter

from app.api.routes import health, onboarding, tasks

router = APIRouter(prefix="/api")
router.include_router(health.router)
router.include_router(onboarding.router)
router.include_router(tasks.router)
