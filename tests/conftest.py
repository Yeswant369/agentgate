import pytest
from fastapi.testclient import TestClient

from gateway.config import get_settings
from gateway.main import create_app


@pytest.fixture()
def client():
    get_settings.cache_clear()
    app = create_app()
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    get_settings.cache_clear()
