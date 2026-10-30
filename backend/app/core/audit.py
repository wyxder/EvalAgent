"""Audit trail helper used by configuration-changing endpoints."""

from __future__ import annotations

import logging
import typing as t

from app.core.observability import get_request_id

logger = logging.getLogger(__name__)


def _safe_json(value: t.Any) -> t.Any:
    if value is None or isinstance(value, (str, int, float, bool, list, dict)):
        return value
    return str(value)[:500]


def record_audit(
    db,
    *,
    action: str,
    target_type: str,
    target_id: int | None = None,
    before_value: t.Any = None,
    after_value: t.Any = None,
    operator: str = "anonymous",
    note: str | None = None,
) -> None:
    """Persist one audit row. Never let auditing break the business request."""

    try:
        from app.models.ops import AuditLog

        db.add(
            AuditLog(
                action=action,
                target_type=target_type,
                target_id=target_id,
                operator=operator,
                before_value=_safe_json(before_value),
                after_value=_safe_json(after_value),
                note=note,
                request_id=get_request_id(),
            )
        )
        db.commit()
    except Exception:
        logger.warning("Failed to persist audit log: %s %s", action, target_type)
        db.rollback()
