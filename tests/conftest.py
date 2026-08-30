import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from gateway.config import get_settings
from gateway.main import create_app


@pytest.fixture()
def client():
    get_settings.cache_clear()
    app = create_app()
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    get_settings.cache_clear()


def _db_available() -> bool:
    try:
        from gateway.db import check_database_ready

        return bool(get_settings().database_url) and check_database_ready()
    except Exception:
        return False


requires_db = pytest.mark.skipif(
    not _db_available(), reason="DATABASE_URL not configured/reachable"
)


@pytest.fixture()
def seeded_product():
    """A throwaway merchant + product with unique IDs; removed afterwards
    along with any transactions/events/webhooks the test created."""
    from gateway.db import get_session_factory
    from gateway.models import (
        Merchant,
        Product,
        Transaction,
        TransactionEvent,
        WebhookEvent,
    )

    suffix = uuid.uuid4().hex[:10]
    m_id, p_id = f"m_test_{suffix}", f"p_test_{suffix}"
    session = get_session_factory()()
    try:
        session.add(Merchant(id=m_id, name=f"Test Merchant {suffix}", category="test"))
        session.add(
            Product(
                id=p_id,
                merchant_id=m_id,
                title=f"Test Product {suffix}",
                description="test fixture",
                price_paise=123_456,
                currency="INR",
            )
        )
        session.commit()
        yield {"merchant_id": m_id, "product_id": p_id, "price_paise": 123_456}
    finally:
        txn_ids = [
            t.id for t in session.query(Transaction).filter(Transaction.product_id == p_id)
        ]
        if txn_ids:
            session.execute(
                delete(TransactionEvent).where(TransactionEvent.transaction_id.in_(txn_ids))
            )
            session.execute(delete(Transaction).where(Transaction.id.in_(txn_ids)))
        session.execute(
            delete(WebhookEvent).where(WebhookEvent.event_id.like(f"evt_test_{suffix}%"))
        )
        session.execute(delete(Product).where(Product.id == p_id))
        session.execute(delete(Merchant).where(Merchant.id == m_id))
        session.commit()
        session.close()


@pytest.fixture()
def stub_provider(monkeypatch):
    """Replace the Razorpay client in the orders route: tests must be able to
    run offline, and CI must never create real provider orders."""
    import gateway.routes.orders as orders_module

    class _StubClient:
        def create_order(self, amount, receipt, notes=None):
            return {"id": f"order_stub_{uuid.uuid4().hex[:12]}", "amount": amount.paise}

    monkeypatch.setattr(orders_module, "RazorpayClient", _StubClient)
    return _StubClient
