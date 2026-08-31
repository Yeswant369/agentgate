"""Thin HTTP client to the deployed AgentGate.

The buyer agent holds ONLY its scoped agent key. It has no Razorpay
credentials and no database access — if the agent is fully compromised, the
worst it can do is send requests the gateway will independently judge. This
separation is the whole thesis: the agent is untrusted, the gateway decides.
"""

import os
import uuid
from typing import Any

import httpx

DEFAULT_BASE = os.environ.get("AGENTGATE_URL", "http://127.0.0.1:8000")


class GatewayClient:
    def __init__(self, agent_key: str, base_url: str = DEFAULT_BASE, timeout: float = 30.0):
        self._agent_key = agent_key
        self._client = httpx.Client(
            base_url=base_url,
            timeout=timeout,
            headers={"X-Agent-Key": agent_key},
        )

    def search_catalog(self, query: str) -> list[dict[str, Any]]:
        r = self._client.get("/api/catalog/products", params={"q": query, "limit": 20})
        r.raise_for_status()
        items: list[dict[str, Any]] = r.json()
        return items

    def get_product(self, product_id: str) -> dict[str, Any]:
        r = self._client.get(f"/api/catalog/products/{product_id}")
        if r.status_code == 404:
            return {"error": "product not found"}
        r.raise_for_status()
        product: dict[str, Any] = r.json()
        return product

    def create_purchase_intent(
        self, product_id: str, claimed_price_paise: int, idempotency_key: str | None = None
    ) -> dict[str, Any]:
        key = idempotency_key or f"agent-{uuid.uuid4().hex}"
        r = self._client.post(
            "/api/purchase-intents",
            headers={"Idempotency-Key": key},
            json={"product_id": product_id, "claimed_price_paise": claimed_price_paise},
        )
        # A deny is a 201 with decision=deny; a 5xx is fail-closed. Return the
        # body either way so the agent sees the gateway's verdict, not an
        # exception it might narrate away.
        body: dict[str, Any]
        try:
            body = r.json()
        except ValueError:
            body = {"error": r.text[:200], "status": r.status_code}
        body["_http_status"] = r.status_code
        body["_idempotency_key"] = key
        return body

    def check_intent_status(self, transaction_id: str) -> dict[str, Any]:
        r = self._client.get(f"/api/purchase-intents/{transaction_id}")
        if r.status_code == 404:
            return {"error": "transaction not found"}
        r.raise_for_status()
        status: dict[str, Any] = r.json()
        return status

    def record_session(self, payload: dict[str, Any]) -> dict[str, Any]:
        r = self._client.post("/api/agent-sessions", json=payload)
        r.raise_for_status()
        out: dict[str, Any] = r.json()
        return out
