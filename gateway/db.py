from sqlalchemy import Engine, create_engine, text

from gateway.config import get_settings

_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        settings = get_settings()
        if not settings.database_url:
            raise RuntimeError("database_url is not configured")
        # pool_pre_ping: Neon's pooler can drop idle connections between
        # serverless invocations; verify before use instead of failing mid-request.
        _engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,
            pool_size=1,
            max_overflow=4,
            connect_args={"connect_timeout": 5},
        )
    return _engine


def check_database_ready() -> bool:
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return True
