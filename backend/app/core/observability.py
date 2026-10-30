"""Request tracing + structured logging primitives.

The platform runs as a single-process FastAPI service. This module keeps the
observability layer dependency-free:

* every HTTP request gets a request id (reused when the client already sends
  ``X-Request-Id``, which the frontend does) so browser errors can be matched
  with backend logs;
* the id is stored in a ``ContextVar`` and injected into log records;
* optional JSON logging keeps the output machine-parsable for log collectors.
"""

from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from contextvars import ContextVar

from starlette.types import ASGIApp, Receive, Scope, Send

REQUEST_ID_HEADER = "X-Request-Id"
_request_id: ContextVar[str] = ContextVar("request_id", default="-")

access_logger = logging.getLogger("app.request")


def get_request_id() -> str:
    return _request_id.get()


def new_request_id() -> str:
    return uuid.uuid4().hex[:16]


class RequestIdFilter(logging.Filter):
    """Inject ``request_id`` into every record, including background threads."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not getattr(record, "request_id", None):
            record.request_id = _request_id.get()
        return True


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        for key in ("http_method", "http_path", "http_status", "duration_ms"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


class RequestContextMiddleware:
    """Attach a request id, echo it in the response and log one access line."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        incoming = headers.get(b"x-request-id", b"").decode("latin-1").strip()
        request_id = incoming[:64] if incoming else new_request_id()
        token = _request_id.set(request_id)
        started = time.perf_counter()
        status_holder = {"code": 500}

        async def send_wrapper(message) -> None:
            if message.get("type") == "http.response.start":
                status_holder["code"] = message.get("status", 500)
                response_headers = [
                    (key, value)
                    for key, value in (message.get("headers") or [])
                    if key.lower() != b"x-request-id"
                ]
                response_headers.append((b"x-request-id", request_id.encode("latin-1")))
                message = {**message, "headers": response_headers}
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 1)
            access_logger.info(
                "%s %s -> %s",
                scope.get("method"),
                scope.get("path"),
                status_holder["code"],
                extra={
                    "http_method": scope.get("method"),
                    "http_path": scope.get("path"),
                    "http_status": status_holder["code"],
                    "duration_ms": duration_ms,
                },
            )
            _request_id.reset(token)


def configure_logging(level_name: str = "INFO", json_mode: bool = False) -> None:
    """Configure the project logger once at startup."""

    level = getattr(logging, level_name.upper(), logging.INFO)
    app_logger = logging.getLogger("app")
    app_logger.setLevel(level)

    if not app_logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        if json_mode:
            handler.setFormatter(JsonLogFormatter())
        else:
            handler.setFormatter(
                logging.Formatter("%(levelname)s:%(name)s:%(request_id)s:%(message)s")
            )
        app_logger.addHandler(handler)

    for handler in app_logger.handlers:
        if not any(isinstance(item, RequestIdFilter) for item in handler.filters):
            handler.addFilter(RequestIdFilter())

    app_logger.propagate = False
