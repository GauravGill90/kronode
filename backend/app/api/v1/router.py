from fastapi import APIRouter

from app.api.v1 import onboarding, dashboard, tasks

api_router = APIRouter()

api_router.include_router(onboarding.router, prefix="/onboarding", tags=["onboarding"])
api_router.include_router(dashboard.router, prefix="", tags=["dashboard"])
api_router.include_router(tasks.router, prefix="", tags=["tasks"])
