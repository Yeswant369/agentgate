from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from gateway.db import get_db
from gateway.models import EvalRun

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


@router.get("")
def latest_metrics(db: Session = Depends(get_db)) -> dict:
    """The most recent eval run's metrics, for the dashboard Metrics page."""
    run = db.scalar(select(EvalRun).order_by(EvalRun.id.desc()).limit(1))
    if run is None:
        return {"available": False}
    return {
        "available": True,
        "run_id": run.id,
        "ran_at": run.ran_at.isoformat(),
        "mode": run.mode,
        "model": run.model,
        "scenario_count": run.scenario_count,
        "metrics": run.metrics,
    }


@router.get("/history")
def metrics_history(limit: int = 20, db: Session = Depends(get_db)) -> list[dict]:
    """Run history — INCLUDING worse early runs. Honesty is visible here."""
    limit = max(1, min(limit, 100))
    rows = db.scalars(select(EvalRun).order_by(EvalRun.id.desc()).limit(limit)).all()
    return [
        {
            "run_id": r.id,
            "ran_at": r.ran_at.isoformat(),
            "mode": r.mode,
            "scenario_count": r.scenario_count,
            "recall": r.metrics.get("confusion_matrix", {}).get("recall", {}).get("point"),
            "fpr": r.metrics.get("confusion_matrix", {}).get("fpr", {}).get("point"),
            "f1": r.metrics.get("confusion_matrix", {}).get("f1"),
        }
        for r in rows
    ]
