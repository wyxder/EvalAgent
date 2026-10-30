"""Operational tables: audit trail and metric result cache."""

from sqlalchemy import Column, DateTime, Float, Integer, String, Text, JSON
from sqlalchemy.sql import func

from app.core.database import Base


class AuditLog(Base):
    """Who changed which configuration, with before/after snapshots."""

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    action = Column(String(100), nullable=False, index=True)
    target_type = Column(String(50), nullable=False, index=True)
    target_id = Column(Integer, nullable=True, index=True)
    operator = Column(String(100), default="anonymous")
    before_value = Column(JSON, nullable=True)
    after_value = Column(JSON, nullable=True)
    note = Column(Text, nullable=True)
    request_id = Column(String(64), nullable=True)
    ip = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=func.now(), index=True)


class EvalMetricCache(Base):
    """Cache of judge results keyed by row + metric + model + prompt version."""

    __tablename__ = "eval_metric_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cache_key = Column(String(64), nullable=False, unique=True, index=True)
    metric_name = Column(String(100), nullable=False)
    model_name = Column(String(200), nullable=True)
    prompt_version = Column(String(50), nullable=True)
    score = Column(Float, nullable=True)
    reason = Column(Text, nullable=True)
    hit_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
