"""Unified API error contract: ``{code, message, detail, request_id}``.

The contract is additive: ``detail`` keeps its FastAPI meaning so every
existing response shape and frontend ``ApiError.detail`` reader keeps working.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.observability import get_request_id

logger = logging.getLogger(__name__)


def _json_safe(value: Any) -> Any:
    """Round-trip through JSON so non-serializable values (e.g. ValueError in
    pydantic ``errors()`` ctx) degrade to strings instead of breaking the 422."""

    try:
        return json.loads(json.dumps(value, ensure_ascii=False, default=str))
    except Exception:
        return str(value)


def _payload(code: str, message: str, detail: Any = None) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "detail": _json_safe(detail),
        "request_id": get_request_id(),
    }


def _status_code_for(exc: HTTPException) -> int:
    return exc.status_code if isinstance(exc.status_code, int) else 500


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, str):
        message = exc.detail
        detail: Any = exc.detail
    else:
        message = "请求处理失败"
        detail = exc.detail
    return JSONResponse(
        status_code=_status_code_for(exc),
        content=_payload(f"http_{_status_code_for(exc)}", message, detail),
        headers=getattr(exc, "headers", None),
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422, content=_payload("validation_error", "请求参数校验失败", exc.errors())
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500, content=_payload("internal_error", "服务器内部错误，请稍后重试", None)
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
