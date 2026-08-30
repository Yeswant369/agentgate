import logging

from fastapi import APIRouter

from gateway.config import get_settings
from gateway.db import check_database_ready
from gateway.errors import problem_response

logger = logging.getLogger("gateway.health")

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("/live")
def liveness() -> dict:
    """Process is up. Says nothing about dependencies — that is /ready's job."""
    return {"status": "live", "service": "agentgate"}


@router.get("/ready")
def readiness():
    """Process can serve real traffic: the database must be reachable.
    Anything less returns 503 — a health check that lies is worse than none."""
    settings = get_settings()
    if not settings.database_url:
        return problem_response(
            status=503,
            title="Not ready",
            detail="database_url is not configured",
        )
    try:
        check_database_ready()
    except Exception:
        logger.exception("readiness check failed")
        return problem_response(status=503, title="Not ready", detail="database unreachable")
    return {"status": "ready", "service": "agentgate", "env": settings.env}
