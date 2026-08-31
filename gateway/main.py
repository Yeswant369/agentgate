from fastapi import FastAPI

from gateway.config import get_settings
from gateway.errors import register_error_handlers
from gateway.logging import configure_logging
from gateway.middleware import RequestIdMiddleware
from gateway.routes.admin import router as admin_router
from gateway.routes.catalog import router as catalog_router
from gateway.routes.decisions import router as decisions_router
from gateway.routes.health import router as health_router
from gateway.routes.intents import router as intents_router
from gateway.routes.metrics import router as metrics_router
from gateway.routes.orders import router as orders_router
from gateway.routes.sessions import router as sessions_router
from gateway.routes.webhooks import router as webhooks_router


def create_app() -> FastAPI:
    configure_logging()
    get_settings()  # fail fast: invalid production config crashes here, at boot

    app = FastAPI(
        title="AgentGate",
        description=(
            "Trust gateway for agentic commerce: every money action "
            "explainable, bounded and gated."
        ),
        version="0.2.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    app.add_middleware(RequestIdMiddleware)
    register_error_handlers(app)
    app.include_router(health_router)
    app.include_router(catalog_router)
    app.include_router(orders_router)
    app.include_router(webhooks_router)
    app.include_router(intents_router)
    app.include_router(admin_router)
    app.include_router(decisions_router)
    app.include_router(sessions_router)
    app.include_router(metrics_router)
    return app


app = create_app()
