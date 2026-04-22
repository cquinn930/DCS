"""Health check endpoints."""

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dcs_api.config import get_settings
from dcs_api.database import get_session

router = APIRouter()
settings = get_settings()


@router.get("/health")
async def health_check() -> dict[str, Any]:
    """Basic health check."""
    return {
        "status": "healthy",
        "version": settings.app_version,
    }


@router.get("/health/ready")
async def readiness_check(
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Readiness check including database connectivity."""
    try:
        await session.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "error"

    all_healthy = db_status == "connected"

    return {
        "status": "ready" if all_healthy else "not_ready",
        "checks": {
            "database": db_status,
        },
    }
