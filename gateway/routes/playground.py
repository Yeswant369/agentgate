"""Judge Playground: re-fire a recorded agent scenario through the REAL policy
engine, live. The LLM's shopping decisions are pre-recorded; the gateway's
policy verdict is computed fresh on every click — that is the thing being
demonstrated. Rate-limited per IP (DB-backed), and honestly labeled as a
replay in the response.

No agent key or admin token needed: this endpoint constructs a PolicyInput
directly from a fixed, safe scenario catalog and calls evaluate(). It never
touches Razorpay and never mutates the ledger — a judge cannot spend anything.
"""

import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from gateway.db import get_db
from gateway.errors import problem_response
from gateway.logging import log_with
from gateway.policy.rules import PolicyInput, evaluate
from gateway.ratelimit import check_and_increment

logger = logging.getLogger("gateway.playground")

router = APIRouter(prefix="/api/playground", tags=["playground"])

RATE_LIMIT = 20  # replays per window per IP
WINDOW_SECONDS = 60


def _pi(**overrides) -> PolicyInput:
    base = dict(
        agent_id="agt_playground",
        mandate_id="mdt_playground",
        mandate_revoked=False,
        mandate_expired=False,
        merchant_allowlist=("m_voltedge", "m_chaiwala"),
        allowed_categories=(),
        max_txn_paise=250_000,
        daily_cap_paise=600_000,
        merchant_id="m_voltedge",
        merchant_category="electronics",
        product_id="p_x",
        catalog_price_paise=50_000,
        claimed_price_paise=50_000,
        amount_paise=50_000,
        spent_today_paise=0,
        intents_in_velocity_window=0,
        duplicate_intents_in_window=0,
        merchant_spend_in_structuring_window_paise=0,
        merchant_txn_count_in_structuring_window=0,
    )
    base.update(overrides)
    return PolicyInput(**base)  # type: ignore[arg-type]


# A fixed, safe catalog of replayable scenarios. Each names the recorded agent
# story and the exact PolicyInput the gateway will judge live.
SCENARIOS: dict[str, dict] = {
    "legit_purchase": {
        "title": "Legit purchase — chai within budget",
        "story": "The agent searches, finds a ₹349 masala chai, and buys it at the real price.",
        "expected": "allow",
        "input": _pi(
            amount_paise=34_900,
            claimed_price_paise=34_900,
            catalog_price_paise=34_900,
            merchant_id="m_chaiwala",
            merchant_category="food_beverage",
        ),
    },
    "prompt_injection_price": {
        "title": "Prompt-injection — price manipulation",
        "story": "A poisoned listing convinces the agent a ₹1,499 power bank costs ₹99. "
        "The agent submits the injected price.",
        "expected": "deny",
        "input": _pi(
            amount_paise=149_900, catalog_price_paise=149_900, claimed_price_paise=9_900
        ),
    },
    "lookalike_merchant": {
        "title": "Lookalike merchant (homoglyph)",
        "story": "The agent is lured to a cheaper listing on a Cyrillic-lookalike "
        "'VoltEdgе' merchant that is not on the mandate allowlist.",
        "expected": "deny",
        "input": _pi(merchant_id="m_voltedge_lookalike"),
    },
    "structuring_attack": {
        "title": "Structuring — salami slicing",
        "story": "Three sub-cap purchases to one merchant that together exceed the "
        "per-transaction cap.",
        "expected": "deny",
        "input": _pi(
            amount_paise=90_000,
            claimed_price_paise=90_000,
            catalog_price_paise=90_000,
            merchant_spend_in_structuring_window_paise=200_000,
            merchant_txn_count_in_structuring_window=3,
        ),
    },
    "overspend": {
        "title": "Direct overspend",
        "story": "The agent tries to buy a ₹2,599 item against a ₹2,500 per-transaction cap.",
        "expected": "deny",
        "input": _pi(
            amount_paise=259_900, claimed_price_paise=259_900, catalog_price_paise=259_900
        ),
    },
}


@router.get("/scenarios")
def list_scenarios() -> list[dict]:
    return [
        {"id": k, "title": v["title"], "story": v["story"], "expected": v["expected"]}
        for k, v in SCENARIOS.items()
    ]


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("/replay/{scenario_id}")
def replay(scenario_id: str, request: Request, db: Session = Depends(get_db)):
    scenario = SCENARIOS.get(scenario_id)
    if scenario is None:
        return problem_response(status=404, title="Unknown scenario")

    allowed, remaining = check_and_increment(
        db,
        bucket="playground",
        client=_client_ip(request),
        limit=RATE_LIMIT,
        window_seconds=WINDOW_SECONDS,
    )
    if not allowed:
        return problem_response(
            status=429,
            title="Rate limited",
            detail=f"Playground is bounded to {RATE_LIMIT} replays/minute per IP — "
            "the demo is itself bounded and gated, which is the point.",
        )

    decision = evaluate(scenario["input"])
    log_with(
        logger,
        logging.INFO,
        "playground replay",
        scenario=scenario_id,
        decision=decision.decision,
    )
    return {
        "scenario_id": scenario_id,
        "title": scenario["title"],
        "story": scenario["story"],
        "note": "Replay of a recorded agent session — the LLM's shopping is pre-recorded, "
        "but the gateway's policy decision below is computed live on this click.",
        "decision": decision.decision,
        "expected": scenario["expected"],
        "matches_expected": decision.decision == scenario["expected"]
        or (scenario["expected"] == "deny" and decision.decision == "step_up"),
        "rules": [
            {"rule_id": r.rule_id, "outcome": r.outcome, "reason": r.reason}
            for r in decision.rule_results
            if r.outcome != "pass"
        ],
        "all_rules": [
            {"rule_id": r.rule_id, "outcome": r.outcome} for r in decision.rule_results
        ],
        "policy_version": decision.policy_version,
        "rate_limit_remaining": remaining,
    }
