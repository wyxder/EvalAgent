"""Lightweight in-process rate limiting for expensive write endpoints.

Only LLM-heavy creation endpoints are limited, because they are the ones that
can burn quota or create long-running jobs. Regular CRUD traffic stays untouched
so the workbench keeps feeling responsive.
"""

from __future__ import annotations

import json
import time
from collections import defaultdict, deque

from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.observability import get_request_id

# Prefixes are matched against the request path.
HEAVY_PATH_PREFIXES = (
    "/api/evaluations",
    "/api/blind-tests",
    "/api/rag-dataset-jobs",
    "/api/rsi/loops",
)


class SlidingWindowLimiter:
    def __init__(self, limit: int, window_seconds: int = 60):
        self.limit = max(1, limit)
        self.window_seconds = max(1, window_seconds)
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> tuple[bool, int]:
        now = time.monotonic()
        window_start = now - self.window_seconds
        hits = self._hits[key]
        while hits and hits[0] <= window_start:
            hits.popleft()
        if len(hits) >= self.limit:
            retry_after = max(1, int(hits[0] + self.window_seconds - now))
            return False, retry_after
        hits.append(now)
        return True, 0


class RateLimitMiddleware:
    """Apply the limiter to POST requests under expensive prefixes."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        enabled: bool = True,
        limit_per_minute: int = 120,
    ):
        self.app = app
        self.enabled = enabled
        self.limiter = SlidingWindowLimiter(limit_per_minute, 60)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if not self.enabled or scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "")
        path = scope.get("path", "")
        if method != "POST" or not path.startswith(HEAVY_PATH_PREFIXES):
            await self.app(scope, receive, send)
            return

        client = scope.get("client") or ("unknown", 0)
        key = str(client[0])
        allowed, retry_after = self.limiter.allow(key)
        if allowed:
            await self.app(scope, receive, send)
            return

        body = json.dumps(
            {
                "code": "rate_limited",
                "message": "请求过于频繁，请稍后再试",
                "detail": "请求过于频繁，请稍后再试",
                "request_id": get_request_id(),
            },
            ensure_ascii=False,
        ).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 429,
                "headers": [
                    (b"content-type", b"application/json; charset=utf-8"),
                    (b"retry-after", str(retry_after).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
