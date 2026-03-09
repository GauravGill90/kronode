from fastapi import APIRouter
from app.api.v1 import onboarding

api_router = APIRouter()
api_router.include_router(onboarding.router)
