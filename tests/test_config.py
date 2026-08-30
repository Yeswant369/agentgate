import pytest
from pydantic import ValidationError

from gateway.config import Settings


def test_dev_allows_missing_database_url():
    settings = Settings(env="dev", database_url="", _env_file=None)
    assert settings.database_url == ""


def test_production_requires_database_url():
    with pytest.raises(ValidationError, match="database_url"):
        Settings(env="production", database_url="", _env_file=None)


def test_production_rejects_wrong_driver_scheme():
    with pytest.raises(ValidationError, match="postgresql\\+psycopg"):
        Settings(
            env="production",
            database_url="postgres://user:pass@host/db",
            _env_file=None,
        )
