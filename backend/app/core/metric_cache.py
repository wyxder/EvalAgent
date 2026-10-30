"""Metric result cache (A2): key = row + metric + model + prompt version."""

from __future__ import annotations

import hashlib
import json
import typing as t

from app.models.ops import EvalMetricCache


def compute_cache_key(
    *,
    row_data: dict[str, t.Any],
    metric_name: str,
    model_name: str,
    prompt_version: str,
    criteria: str = "",
) -> str:
    """Stable hash of the scoring inputs. Internal keys are ignored."""

    public_row = {
        key: value
        for key, value in row_data.items()
        if not str(key).startswith("_")
    }
    payload = {
        "row": public_row,
        "metric": metric_name,
        "model": model_name,
        "prompt_version": prompt_version,
        "criteria": criteria or "",
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def get_cached(db, cache_key: str) -> dict[str, t.Any] | None:
    try:
        item = (
            db.query(EvalMetricCache)
            .filter(EvalMetricCache.cache_key == cache_key)
            .first()
        )
    except Exception:
        return None
    if item is None:
        return None
    return {"score": item.score, "reason": item.reason}


def store_cache(
    db,
    *,
    cache_key: str,
    metric_name: str,
    model_name: str,
    prompt_version: str,
    score: float | None,
    reason: str,
) -> None:
    """Add a cache row to the current transaction (caller commits)."""

    if score is None:
        return
    try:
        db.add(
            EvalMetricCache(
                cache_key=cache_key,
                metric_name=metric_name,
                model_name=model_name,
                prompt_version=prompt_version,
                score=float(score),
                reason=reason,
            )
        )
    except Exception:
        # A duplicate cache key just means another row already stored it.
        pass
