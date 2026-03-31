from fastapi import APIRouter

from app.api.v1 import onboarding, dashboard, tasks, jira, conventions, skills, api_keys, context, webhooks, usage

api_router = APIRouter()

api_router.include_router(onboarding.router, prefix="/onboarding", tags=["onboarding"])
api_router.include_router(dashboard.router, prefix="", tags=["dashboard"])
api_router.include_router(tasks.router, prefix="", tags=["tasks"])
api_router.include_router(jira.router, prefix="", tags=["jira"])
api_router.include_router(conventions.router, prefix="", tags=["conventions"])
api_router.include_router(skills.router, prefix="", tags=["skills"])
api_router.include_router(api_keys.router, prefix="", tags=["api-keys"])
api_router.include_router(context.router, prefix="", tags=["context"])
api_router.include_router(webhooks.router, prefix="", tags=["webhooks"])
api_router.include_router(usage.router, prefix="", tags=["usage"])
