from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from gateway.db import get_db
from gateway.models import Agent, AgentSession, new_id
from gateway.security import hash_agent_key

router = APIRouter(prefix="/api/agent-sessions", tags=["agent-sessions"])


class SessionIn(BaseModel):
    intent: str = Field(min_length=1, max_length=2000)
    scenario: str | None = Field(default=None, max_length=100)
    transcript: list[dict[str, Any]] = Field(max_length=2000)
    claimed: dict[str, Any]
    actual: dict[str, Any]
    honest: bool | None


def _auth_agent(db: Session, agent_key: str) -> Agent:
    agent = db.scalar(select(Agent).where(Agent.api_key_hash == hash_agent_key(agent_key)))
    if agent is None:
        raise HTTPException(status_code=401, detail="invalid agent key")
    return agent


@router.post("", status_code=201)
def record_session(
    body: SessionIn,
    x_agent_key: str = Header(min_length=8),
    db: Session = Depends(get_db),
) -> dict:
    agent = _auth_agent(db, x_agent_key)
    session = AgentSession(
        id=new_id("ses"),
        agent_id=agent.id,
        intent=body.intent,
        scenario=body.scenario,
        transcript=body.transcript,
        claimed=body.claimed,
        actual=body.actual,
        honest=body.honest,
    )
    db.add(session)
    return {"session_id": session.id}


@router.get("")
def list_sessions(limit: int = 50, db: Session = Depends(get_db)) -> list[dict]:
    limit = max(1, min(limit, 200))
    rows = db.scalars(
        select(AgentSession).order_by(AgentSession.created_at.desc()).limit(limit)
    ).all()
    return [
        {
            "session_id": s.id,
            "agent_id": s.agent_id,
            "intent": s.intent,
            "scenario": s.scenario,
            "honest": s.honest,
            "claimed": s.claimed,
            "actual": s.actual,
            "created_at": s.created_at.isoformat(),
        }
        for s in rows
    ]


@router.get("/{session_id}")
def get_session(session_id: str, db: Session = Depends(get_db)) -> dict:
    s = db.get(AgentSession, session_id)
    if s is None:
        raise HTTPException(status_code=404, detail="session not found")
    return {
        "session_id": s.id,
        "agent_id": s.agent_id,
        "intent": s.intent,
        "scenario": s.scenario,
        "transcript": s.transcript,
        "claimed": s.claimed,
        "actual": s.actual,
        "honest": s.honest,
        "created_at": s.created_at.isoformat(),
    }
