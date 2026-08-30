"""Razorpay REST client (test mode).

Deliberately httpx against the documented REST API rather than the SDK:
explicit timeouts on every call, typed errors the gateway can branch on,
and a swappable transport so tests exercise the real request/response path
without the network.
"""

import logging
from typing import Any

import httpx

from gateway.config import get_settings
from gateway.logging import log_with
from gateway.money import Money

logger = logging.getLogger("gateway.razorpay")

BASE_URL = "https://api.razorpay.com/v1"
TIMEOUT_SECONDS = 10.0


class RazorpayError(Exception):
    """Base for all Razorpay client failures."""


class RazorpayAPIError(RazorpayError):
    """Razorpay answered with an error (4xx/5xx). Not retryable blindly."""

    def __init__(self, status: int, code: str, description: str):
        self.status, self.code, self.description = status, code, description
        super().__init__(f"razorpay api error {status} {code}: {description}")


class RazorpayUnavailable(RazorpayError):
    """Timeout or connection failure. The transaction stays in a safe state."""


class RazorpayClient:
    def __init__(self, transport: httpx.BaseTransport | None = None):
        settings = get_settings()
        if not settings.razorpay_key_id or not settings.razorpay_key_secret:
            raise RuntimeError("Razorpay credentials are not configured")
        self._client = httpx.Client(
            base_url=BASE_URL,
            auth=(settings.razorpay_key_id, settings.razorpay_key_secret),
            timeout=TIMEOUT_SECONDS,
            transport=transport,
        )

    def _request(
        self, method: str, path: str, json: dict | None = None, params: dict | None = None
    ) -> dict:
        try:
            resp = self._client.request(method, path, json=json, params=params)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            log_with(logger, logging.WARNING, "razorpay unavailable", path=path, error=str(exc))
            raise RazorpayUnavailable(str(exc)) from exc
        if resp.status_code >= 400:
            try:
                err = resp.json().get("error", {})
            except ValueError:
                err = {}
            raise RazorpayAPIError(
                resp.status_code,
                err.get("code", "unknown"),
                err.get("description", resp.text[:200]),
            )
        data: dict[str, Any] = resp.json()
        return data

    def create_order(
        self, amount: Money, receipt: str, notes: dict[str, str] | None = None
    ) -> dict:
        """POST /orders — amount is already integer paise, which is exactly
        the unit Razorpay's API expects. No conversion, no rounding."""
        payload = {
            "amount": amount.paise,
            "currency": amount.currency,
            "receipt": receipt,
            "notes": notes or {},
        }
        order = self._request("POST", "/orders", json=payload)
        log_with(
            logger,
            logging.INFO,
            "razorpay order created",
            order_id=order.get("id"),
            amount_paise=amount.paise,
            receipt=receipt,
        )
        return order

    def get_order(self, order_id: str) -> dict:
        return self._request("GET", f"/orders/{order_id}")

    def list_orders(self, count: int = 100, skip: int = 0) -> list[dict]:
        data = self._request("GET", "/orders", params={"count": count, "skip": skip})
        items: list[dict] = data.get("items", [])
        return items

    def get_payment(self, payment_id: str) -> dict:
        return self._request("GET", f"/payments/{payment_id}")

    def refund_payment(self, payment_id: str, amount: Money) -> dict:
        return self._request(
            "POST", f"/payments/{payment_id}/refund", json={"amount": amount.paise}
        )
