import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse

from gateway.logging import request_id_var

logger = logging.getLogger("gateway.errors")

PROBLEM_CONTENT_TYPE = "application/problem+json"


def problem_response(
    *, status: int, title: str, detail: str = "", type_: str = "about:blank"
) -> JSONResponse:
    """RFC 7807 problem details. Every error path in the API returns this
    shape — clients and judges see one consistent envelope, never a traceback."""
    body = {
        "type": type_,
        "title": title,
        "status": status,
        "detail": detail,
        "request_id": request_id_var.get(),
    }
    return JSONResponse(body, status_code=status, media_type=PROBLEM_CONTENT_TYPE)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        from http import HTTPStatus

        try:
            title = HTTPStatus(exc.status_code).phrase
        except ValueError:
            title = "HTTP error"
        return problem_response(
            status=exc.status_code, title=title, detail=str(exc.detail or "")
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        return problem_response(
            status=422,
            title="Validation error",
            detail="; ".join(
                f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()
            ),
        )

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception):
        logger.exception("unhandled exception")
        return problem_response(
            status=500,
            title="Internal server error",
            detail="An unexpected error occurred. Reference this request_id.",
        )
