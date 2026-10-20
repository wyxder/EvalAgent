"""Deterministic policy helpers for the RSI self-evolution loop.

Everything in this module is pure or read-only: budget resolution, stable
holdout splitting, metric summarisation, threshold-independent acceptance and
fitness calculation. Keeping it free of orchestration makes the anti reward
hacking rules easy to unit test.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable

from app.core.config import settings


DEFAULT_BUDGET: dict[str, Any] = {
    "max_iterations": settings.RSI_MAX_ITERATIONS,
    "max_rows_per_iteration": settings.RSI_MAX_ROWS_PER_ITERATION,
    "max_llm_calls": settings.RSI_MAX_LLM_CALLS,
    "max_minutes": settings.RSI_MAX_MINUTES,
    "max_proposals_per_iteration": settings.RSI_MAX_PROPOSALS_PER_ITERATION,
    "max_consecutive_no_gain": 2,
}

DEFAULT_ACCEPTANCE_POLICY: dict[str, Any] = {
    "objective": {
        "metric": None,
        "direction": "maximize",
        "min_gain": settings.RSI_MIN_OBJECTIVE_GAIN,
        "mode": "reference_pass_rate",
    },
    "constraints": {
        "max_metric_drop": settings.RSI_MAX_METRIC_DROP,
        "max_new_failures": 0,
        "max_error_rate_delta": settings.RSI_MAX_ERROR_RATE_DELTA,
        "protected_metrics": [],
    },
    "sampling": {
        "holdout_ratio": settings.RSI_HOLDOUT_RATIO,
        "min_rows": settings.RSI_HOLDOUT_MIN_ROWS,
        "min_rows_for_auto_accept": settings.RSI_HOLDOUT_MIN_ROWS_AUTO,
    },
    "review": {
        "auto_apply_low_risk": settings.RSI_AUTO_APPLY_LOW_RISK,
        "require_human_for": [
            "prompt_override",
            "pass_threshold",
            "metric_config",
            "endpoint_template",
        ],
    },
}


@dataclass
class RowScore:
    """One evaluated dataset row reduced to the fields policy needs."""

    row_id: int
    row_index: int
    is_pass: bool | None = None
    error: str | None = None
    scores: dict[str, float | None] = field(default_factory=dict)
    reasons: dict[str, str] = field(default_factory=dict)


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"pass", "yes", "true", "1"}:
            return 1.0
        if normalized in {"fail", "no", "false", "0"}:
            return 0.0
        match = re.search(r"-?\d+(?:\.\d+)?", value)
        if match:
            return float(match.group(0))
    return None


def merge_budget(raw: dict[str, Any] | None) -> dict[str, Any]:
    budget = dict(DEFAULT_BUDGET)
    for key, value in (raw or {}).items():
        if value is not None:
            budget[key] = value
    return budget


def merge_acceptance_policy(
    raw: dict[str, Any] | None,
    *,
    auto_apply_low_risk: bool | None = None,
) -> dict[str, Any]:
    """Deep merge a (possibly partial) payload over the documented defaults."""

    merged = {
        "objective": dict(DEFAULT_ACCEPTANCE_POLICY["objective"]),
        "constraints": dict(DEFAULT_ACCEPTANCE_POLICY["constraints"]),
        "sampling": dict(DEFAULT_ACCEPTANCE_POLICY["sampling"]),
        "review": {
            **DEFAULT_ACCEPTANCE_POLICY["review"],
            "require_human_for": list(DEFAULT_ACCEPTANCE_POLICY["review"]["require_human_for"]),
        },
    }
    raw = raw or {}
    for section in ("objective", "constraints", "sampling", "review"):
        payload = raw.get(section)
        if not isinstance(payload, dict):
            continue
        for key, value in payload.items():
            if value is not None:
                merged[section][key] = value
    if auto_apply_low_risk is not None:
        merged["review"]["auto_apply_low_risk"] = bool(auto_apply_low_risk)
    return merged


def frozen_reference_thresholds(snapshot: dict[str, Any] | None) -> dict[str, float]:
    """Freeze per-metric reference thresholds from the baseline snapshot.

    Metrics without an explicit ``pass_threshold`` fall back to the documented
    ``0.7`` reference so acceptance never depends on the candidate's own
    thresholds.
    """

    thresholds: dict[str, float] = {}
    for item in (snapshot or {}).get("metrics") or []:
        definition = item.get("metric_definition") or {}
        name = definition.get("name")
        if not name:
            continue
        threshold = item.get("pass_threshold")
        try:
            thresholds[str(name)] = float(threshold) if threshold is not None else 0.7
        except (TypeError, ValueError):
            thresholds[str(name)] = 0.7
    return thresholds


def stable_bucket(loop_id: int, dataset_row_id: int) -> int:
    digest = hashlib.md5(f"{loop_id}:{dataset_row_id}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 100


def split_row_ids(
    loop_id: int,
    row_ids: Iterable[int],
    holdout_ratio: float,
) -> tuple[list[int], list[int]]:
    """Stable train/holdout split; the same loop always yields the same split."""

    ratio = max(0.0, min(float(holdout_ratio or 0.0), 1.0))
    train: list[int] = []
    holdout: list[int] = []
    for row_id in row_ids:
        bucket = stable_bucket(loop_id, int(row_id))
        if ratio > 0 and bucket < ratio * 100:
            holdout.append(int(row_id))
        else:
            train.append(int(row_id))
    return train, holdout


def resolve_holdout(loop, row_ids: Iterable[int]) -> dict[str, Any]:
    """Resolve the loop's holdout configuration against the actual rows."""

    config = loop.holdout_config or {}
    ratio = config.get("holdout_ratio", settings.RSI_HOLDOUT_RATIO)
    try:
        ratio = float(ratio)
    except (TypeError, ValueError):
        ratio = settings.RSI_HOLDOUT_RATIO
    try:
        min_rows = int(config.get("min_rows", settings.RSI_HOLDOUT_MIN_ROWS))
    except (TypeError, ValueError):
        min_rows = settings.RSI_HOLDOUT_MIN_ROWS
    try:
        min_rows_for_auto = int(
            config.get("min_rows_for_auto_accept", settings.RSI_HOLDOUT_MIN_ROWS_AUTO)
        )
    except (TypeError, ValueError):
        min_rows_for_auto = settings.RSI_HOLDOUT_MIN_ROWS_AUTO

    ids = [int(item) for item in row_ids]
    train_ids, holdout_ids = split_row_ids(loop.id, ids, ratio)
    enabled = bool(holdout_ids) and len(holdout_ids) >= min_rows and len(train_ids) >= 1
    return {
        "ratio": ratio,
        "min_rows": min_rows,
        "min_rows_for_auto_accept": min_rows_for_auto,
        "train_row_ids": train_ids,
        "holdout_row_ids": holdout_ids,
        "enabled": enabled,
        "disabled_reason": None
        if enabled
        else (
            "holdout 比例为 0"
            if ratio <= 0
            else f"holdout 行数 {len(holdout_ids)} 少于最小要求 {min_rows}"
        ),
    }


def load_eval_rows(db, task_id: int, row_ids: Iterable[int] | None = None) -> list[RowScore]:
    """Load evaluated rows in a policy-friendly shape."""

    from app.models.evaluation import EvalRowResult

    query = db.query(EvalRowResult).filter(EvalRowResult.eval_task_id == task_id)
    if row_ids is not None:
        ids = [int(item) for item in row_ids]
        if not ids:
            return []
        query = query.filter(EvalRowResult.dataset_row_id.in_(ids))

    rows: list[RowScore] = []
    for result in query.order_by(EvalRowResult.row_index).all():
        scores: dict[str, float | None] = {}
        reasons: dict[str, str] = {}
        for name, raw in (result.metric_scores or {}).items():
            if isinstance(raw, dict):
                scores[name] = _as_float(raw.get("score"))
                reasons[name] = str(raw.get("reason") or "")
            else:
                scores[name] = _as_float(raw)
        rows.append(
            RowScore(
                row_id=result.dataset_row_id,
                row_index=result.row_index,
                is_pass=result.is_pass,
                error=result.error,
                scores=scores,
                reasons=reasons,
            )
        )
    return rows


def reference_row_pass(row: RowScore, thresholds: dict[str, float]) -> bool:
    """Row pass under frozen reference thresholds, independent of candidate config."""

    if not thresholds:
        return bool(row.is_pass)
    for metric, threshold in thresholds.items():
        if threshold is None:
            continue
        score = row.scores.get(metric)
        if score is None:
            return False
        if score < float(threshold):
            return False
    return True


def summarize_rows(
    rows: list[RowScore],
    thresholds: dict[str, float],
    metric_names: Iterable[str] | None = None,
) -> dict[str, Any]:
    names = list(metric_names or thresholds.keys())
    total = len(rows)
    pass_flags = [reference_row_pass(row, thresholds) for row in rows]
    pass_count = sum(1 for flag in pass_flags if flag)
    error_count = sum(1 for row in rows if row.error)
    native_flags = [bool(row.is_pass) for row in rows if row.is_pass is not None]

    metric_stats: dict[str, Any] = {}
    for name in names:
        values = [row.scores.get(name) for row in rows]
        numeric = [value for value in values if value is not None]
        stats: dict[str, Any] = {
            "mean": round(sum(numeric) / len(numeric), 6) if numeric else None,
            "min": min(numeric) if numeric else None,
            "max": max(numeric) if numeric else None,
            "count": len(numeric),
            "error_count": total - len(numeric),
            "pass_rate": None,
        }
        threshold = thresholds.get(name)
        if threshold is not None and total:
            metric_pass = sum(
                1
                for row in rows
                if row.scores.get(name) is not None
                and float(row.scores[name]) >= float(threshold)
            )
            stats["pass_rate"] = round(metric_pass / total, 6)
        metric_stats[name] = stats

    return {
        "total": total,
        "pass_count": pass_count,
        "fail_count": total - pass_count,
        "error_count": error_count,
        "pass_rate": round(pass_count / total, 6) if total else 0.0,
        "error_rate": round(error_count / total, 6) if total else 0.0,
        "native_pass_rate": (
            round(sum(1 for flag in native_flags if flag) / len(native_flags), 6)
            if native_flags
            else None
        ),
        "metric_stats": metric_stats,
    }


def objective_value(
    mode: str,
    metric: str | None,
    rows: list[RowScore],
    thresholds: dict[str, float],
) -> float | None:
    if not rows:
        return None
    if mode == "metric_mean":
        if not metric:
            return None
        numeric = [row.scores.get(metric) for row in rows]
        values = [value for value in numeric if value is not None]
        return round(sum(values) / len(values), 6) if values else None
    return round(sum(1 for row in rows if reference_row_pass(row, thresholds)) / len(rows), 6)


def _slice_by_ids(rows: list[RowScore], ids: set[int]) -> list[RowScore]:
    return [row for row in rows if int(row.row_id) in ids]


def _metric_mean(summary: dict[str, Any], metric: str) -> float | None:
    stats = (summary.get("metric_stats") or {}).get(metric) or {}
    return stats.get("mean")


def _mean_of_metric_means(summary: dict[str, Any]) -> float | None:
    values = [
        stats.get("mean")
        for stats in (summary.get("metric_stats") or {}).values()
        if stats.get("mean") is not None
    ]
    return sum(values) / len(values) if values else None


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def _delta_summary(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, Any]:
    deltas: dict[str, Any] = {
        "pass_rate": round((candidate.get("pass_rate") or 0) - (baseline.get("pass_rate") or 0), 6),
        "error_rate": round(
            (candidate.get("error_rate") or 0) - (baseline.get("error_rate") or 0), 6
        ),
        "pass_count": int(candidate.get("pass_count") or 0) - int(baseline.get("pass_count") or 0),
        "fail_count": int(candidate.get("fail_count") or 0) - int(baseline.get("fail_count") or 0),
        "metrics": {},
    }
    for name, base_stats in (baseline.get("metric_stats") or {}).items():
        cand_stats = (candidate.get("metric_stats") or {}).get(name) or {}
        base_mean = base_stats.get("mean")
        cand_mean = cand_stats.get("mean")
        base_pass = base_stats.get("pass_rate")
        cand_pass = cand_stats.get("pass_rate")
        deltas["metrics"][name] = {
            "mean_delta": (
                round(cand_mean - base_mean, 6)
                if base_mean is not None and cand_mean is not None
                else None
            ),
            "pass_rate_delta": (
                round(cand_pass - base_pass, 6)
                if base_pass is not None and cand_pass is not None
                else None
            ),
        }
    return deltas


def _row_migration(
    baseline_rows: list[RowScore],
    candidate_rows: list[RowScore],
    ids: set[int],
    thresholds: dict[str, float],
) -> dict[str, int]:
    baseline_map = {int(row.row_id): row for row in baseline_rows}
    candidate_map = {int(row.row_id): row for row in candidate_rows}
    fixed = new_failures = still_failing = still_passing = new_errors = 0
    for row_id in ids:
        base = baseline_map.get(row_id)
        cand = candidate_map.get(row_id)
        if base is None or cand is None:
            continue
        base_pass = reference_row_pass(base, thresholds)
        cand_pass = reference_row_pass(cand, thresholds)
        if not base_pass and cand_pass:
            fixed += 1
        elif base_pass and not cand_pass:
            new_failures += 1
        elif base_pass and cand_pass:
            still_passing += 1
        else:
            still_failing += 1
        if cand.error and not base.error:
            new_errors += 1
    return {
        "fixed": fixed,
        "new_failures": new_failures,
        "still_failing": still_failing,
        "still_passing": still_passing,
        "new_errors": new_errors,
    }


def judge_iteration(
    *,
    baseline_rows: list[RowScore],
    candidate_rows: list[RowScore],
    train_row_ids: Iterable[int],
    holdout_row_ids: Iterable[int],
    holdout_enabled: bool,
    policy: dict[str, Any],
    objective_mode: str,
    objective_metric: str | None,
    reference_thresholds: dict[str, float],
    objective_target: float | None = None,
) -> dict[str, Any]:
    """Threshold-independent acceptance judgement for one iteration."""

    train_ids = {int(item) for item in train_row_ids}
    holdout_ids = {int(item) for item in holdout_row_ids}
    metric_names = list(reference_thresholds.keys())

    baseline_full = summarize_rows(baseline_rows, reference_thresholds, metric_names)
    candidate_full = summarize_rows(candidate_rows, reference_thresholds, metric_names)
    baseline_holdout = summarize_rows(
        _slice_by_ids(baseline_rows, holdout_ids), reference_thresholds, metric_names
    )
    candidate_holdout = summarize_rows(
        _slice_by_ids(candidate_rows, holdout_ids), reference_thresholds, metric_names
    )
    baseline_accept = baseline_holdout if holdout_enabled else baseline_full
    candidate_accept = candidate_holdout if holdout_enabled else candidate_full
    baseline_accept_rows = (
        _slice_by_ids(baseline_rows, holdout_ids) if holdout_enabled else baseline_rows
    )
    candidate_accept_rows = (
        _slice_by_ids(candidate_rows, holdout_ids) if holdout_enabled else candidate_rows
    )

    baseline_objective = objective_value(
        objective_mode, objective_metric, baseline_accept_rows, reference_thresholds
    )
    candidate_objective = objective_value(
        objective_mode, objective_metric, candidate_accept_rows, reference_thresholds
    )
    gain = (
        round(candidate_objective - baseline_objective, 6)
        if baseline_objective is not None and candidate_objective is not None
        else None
    )

    constraints_cfg = policy.get("constraints") or {}
    max_metric_drop = float(
        constraints_cfg.get("max_metric_drop", settings.RSI_MAX_METRIC_DROP)
    )
    max_new_failures = int(constraints_cfg.get("max_new_failures", 0) or 0)
    max_error_delta = float(
        constraints_cfg.get("max_error_rate_delta", settings.RSI_MAX_ERROR_RATE_DELTA)
    )
    protected_metrics = constraints_cfg.get("protected_metrics") or []
    if not protected_metrics:
        protected_metrics = [
            name
            for name in metric_names
            if not (objective_mode == "metric_mean" and objective_metric and name == objective_metric)
        ]

    checks: list[dict[str, Any]] = []
    violations: list[str] = []

    for metric in protected_metrics:
        if metric not in metric_names:
            continue
        base_mean = _metric_mean(baseline_accept, metric)
        cand_mean = _metric_mean(candidate_accept, metric)
        if base_mean is None:
            continue
        if cand_mean is None:
            detail = f"指标 {metric} 在候选评估中无法评分"
            checks.append({"name": f"metric_drop:{metric}", "ok": False, "detail": detail})
            violations.append(detail)
            continue
        drop = round(base_mean - cand_mean, 6)
        ok = drop <= max_metric_drop + 1e-9
        checks.append(
            {
                "name": f"metric_drop:{metric}",
                "ok": ok,
                "detail": (
                    f"{metric} 均值变化 {round(cand_mean - base_mean, 6):+}"
                    f"（允许下降 {max_metric_drop}）"
                ),
            }
        )
        if not ok:
            violations.append(f"受保护指标 {metric} 均值下降 {drop}，超过 {max_metric_drop}")

    error_delta = round(
        float(candidate_accept.get("error_rate") or 0)
        - float(baseline_accept.get("error_rate") or 0),
        6,
    )
    error_ok = error_delta <= max_error_delta + 1e-9
    checks.append(
        {
            "name": "error_rate",
            "ok": error_ok,
            "detail": f"错误率变化 {error_delta:+}（允许上升 {max_error_delta}）",
        }
    )
    if not error_ok:
        violations.append(f"错误率上升 {error_delta}，超过 {max_error_delta}")

    migration = _row_migration(
        baseline_rows,
        candidate_rows,
        holdout_ids if holdout_enabled else {row.row_id for row in baseline_rows},
        reference_thresholds,
    )
    new_failures_ok = migration["new_failures"] <= max_new_failures
    checks.append(
        {
            "name": "new_failures",
            "ok": new_failures_ok,
            "detail": f"新增失败 {migration['new_failures']} 条（允许 {max_new_failures} 条）",
        }
    )
    if not new_failures_ok:
        violations.append(
            f"新增失败 {migration['new_failures']} 条，超过 {max_new_failures} 条"
        )

    objective_cfg = policy.get("objective") or {}
    min_gain = float(objective_cfg.get("min_gain", settings.RSI_MIN_OBJECTIVE_GAIN))
    sampling_cfg = policy.get("sampling") or {}
    min_rows_for_auto = int(
        sampling_cfg.get("min_rows_for_auto_accept", settings.RSI_HOLDOUT_MIN_ROWS_AUTO)
    )
    holdout_rows = len(holdout_ids)

    if not candidate_rows:
        decision = "rejected"
        reason = "候选评估没有产生任何行结果"
    elif baseline_objective is None or candidate_objective is None:
        decision = "inconclusive"
        reason = "基线或候选的目标指标无法计算，无法判定"
    elif violations:
        decision = "rejected"
        reason = "；".join(violations)
    elif gain is None or gain <= 0:
        decision = "rejected"
        reason = f"目标指标未提升（增益 {gain}）"
    elif gain + 1e-9 < min_gain:
        decision = "inconclusive"
        reason = f"增益 {gain} 小于最小要求 {min_gain}"
    elif not holdout_enabled:
        decision = "inconclusive"
        reason = "holdout 未启用或样本不足，只能由人工确认"
    else:
        decision = "accepted"
        reason = f"holdout 目标增益 {gain} 达到 {min_gain}，且全部约束满足"

    auto_eligible = (
        decision == "accepted"
        and holdout_enabled
        and holdout_rows >= min_rows_for_auto
    )

    target = objective_target if objective_target is not None else 1.0
    baseline_mean = _mean_of_metric_means(baseline_accept)
    candidate_mean = _mean_of_metric_means(candidate_accept)
    objective_norm = 0.0
    mean_norm = 0.0
    if (
        baseline_objective is not None
        and candidate_objective is not None
        and target > baseline_objective
    ):
        objective_norm = _clamp(
            (candidate_objective - baseline_objective) / (target - baseline_objective)
        )
    if baseline_mean is not None and candidate_mean is not None:
        denominator = max(1e-6, 1.0 - baseline_mean)
        mean_norm = _clamp((candidate_mean - baseline_mean) / denominator)
    fitness = round(0.6 * objective_norm + 0.4 * mean_norm, 6)

    return {
        "decision": decision,
        "recommended": decision,
        "reason": reason,
        "objective": {
            "mode": objective_mode,
            "metric": objective_metric,
            "baseline": baseline_objective,
            "candidate": candidate_objective,
            "gain": gain,
            "target": objective_target,
            "min_gain": min_gain,
        },
        "constraints": checks,
        "violations": violations,
        "holdout": {
            "enabled": holdout_enabled,
            "rows": holdout_rows,
            "train_rows": len(train_ids),
            "min_rows_for_auto_accept": min_rows_for_auto,
        },
        "migration": migration,
        "fitness": fitness,
        "auto_accept_eligible": auto_eligible,
    }


def build_iteration_metrics(
    *,
    baseline_rows: list[RowScore],
    candidate_rows: list[RowScore],
    train_row_ids: Iterable[int],
    holdout_row_ids: Iterable[int],
    holdout_enabled: bool,
    policy: dict[str, Any],
    objective_mode: str,
    objective_metric: str | None,
    reference_thresholds: dict[str, float],
    objective_target: float | None,
    validation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    judge = judge_iteration(
        baseline_rows=baseline_rows,
        candidate_rows=candidate_rows,
        train_row_ids=train_row_ids,
        holdout_row_ids=holdout_row_ids,
        holdout_enabled=holdout_enabled,
        policy=policy,
        objective_mode=objective_mode,
        objective_metric=objective_metric,
        reference_thresholds=reference_thresholds,
        objective_target=objective_target,
    )

    train_ids = {int(item) for item in train_row_ids}
    holdout_ids = {int(item) for item in holdout_row_ids}

    def _pack(rows_base: list[RowScore], rows_cand: list[RowScore]) -> dict[str, Any]:
        base_summary = summarize_rows(rows_base, reference_thresholds)
        cand_summary = summarize_rows(rows_cand, reference_thresholds)
        return {
            "baseline": base_summary,
            "candidate": cand_summary,
            "delta": _delta_summary(base_summary, cand_summary),
        }

    baseline_full = summarize_rows(baseline_rows, reference_thresholds)
    candidate_full = summarize_rows(candidate_rows, reference_thresholds)
    return {
        "baseline": baseline_full,
        "candidate": candidate_full,
        "delta": _delta_summary(baseline_full, candidate_full),
        "train": _pack(
            _slice_by_ids(baseline_rows, train_ids), _slice_by_ids(candidate_rows, train_ids)
        ),
        "holdout": _pack(
            _slice_by_ids(baseline_rows, holdout_ids),
            _slice_by_ids(candidate_rows, holdout_ids),
        ),
        "decision_metrics": judge,
        "objective": judge["objective"],
        "validation": validation or {},
        "reference_thresholds": reference_thresholds,
    }


def resolve_budget(loop) -> dict[str, Any]:
    return merge_budget(loop.budget or {})


def estimate_llm_calls(total_rows: int, llm_metric_count: int, budget: dict[str, Any]) -> int:
    sample_rows = min(
        max(int(total_rows), 0), int(budget.get("max_rows_per_iteration") or total_rows)
    )
    return sample_rows * max(int(llm_metric_count), 0) + 2


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def elapsed_minutes(started_at: datetime | None) -> float:
    started = _aware(started_at)
    if started is None:
        return 0.0
    return max(0.0, (datetime.now(timezone.utc) - started).total_seconds() / 60.0)


def budget_stop_reason(
    loop,
    *,
    next_estimate: int,
    llm_metric_count: int,
) -> str | None:
    """Return a readable stop reason when the loop must not start another round."""

    budget = resolve_budget(loop)
    usage = loop.usage or {}

    if int(loop.current_iteration or 0) >= int(budget.get("max_iterations") or 1):
        return f"达到最大迭代轮次 {budget.get('max_iterations')}"

    used_calls = int(usage.get("llm_calls") or 0)
    if used_calls + int(next_estimate) > int(budget.get("max_llm_calls") or 0):
        return (
            f"LLM 调用预算不足（已用 {used_calls}，预计还需 {next_estimate}，"
            f"上限 {budget.get('max_llm_calls')}）"
        )

    elapsed = float(usage.get("elapsed_ms") or 0) / 60000.0
    if elapsed == 0:
        elapsed = elapsed_minutes(loop.started_at)
    if elapsed >= float(budget.get("max_minutes") or 0):
        return f"运行时长达到上限 {budget.get('max_minutes')} 分钟"

    consecutive = int(usage.get("consecutive_no_gain") or 0)
    if consecutive >= int(budget.get("max_consecutive_no_gain") or 2):
        return f"连续 {consecutive} 轮没有达到最小增益"
    return None


def count_llm_metric_calls(rows: list[RowScore]) -> int:
    """Approximate Judge calls from persisted row results (one per scored metric)."""

    return sum(1 for row in rows for value in row.scores.values() if value is not None)
