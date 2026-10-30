"""Audit trail read endpoints (B8)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.ops import AuditLog

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])


def _serialize(item: AuditLog) -> dict:
    return {
        "id": item.id,
        "action": item.action,
        "target_type": item.target_type,
        "target_id": item.target_id,
        "operator": item.operator,
        "before_value": item.before_value,
        "after_value": item.after_value,
        "note": item.note,
        "request_id": item.request_id,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


@router.get("")
def list_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    target_type: str | None = Query(None),
    action: str | None = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(AuditLog)
    if target_type:
        query = query.filter(AuditLog.target_type == target_type)
    if action:
        query = query.filter(AuditLog.action == action)

    total = query.count()
    items = (
        query.order_by(AuditLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_serialize(item) for item in items],
    }
