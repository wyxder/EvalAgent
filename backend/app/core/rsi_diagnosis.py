"""Failure diagnosis for RSI.

Rule aggregation is always available and deterministic. The LLM clustering
layer is optional: when the model is unavailable or returns invalid JSON we fall
back to rule clusters and mark ``fallback=true``. Callers must pass train-only
rows; holdout rows are filtered defensively here as well.
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.core.prompt_manager import (
    RSI_DIAGNOSIS_OUTPUT_SCHEMA,
    RSI_DIAGNOSIS_SYSTEM_PROMPT,
)
from app.core.rsi_policy import RowScore, reference_row_pass


ROOT_CAUSE_TYPES = {
    "prompt_ambiguity",
    "missing_field",
    "judge_misconfiguration",
    "retrieval_gap",
    "answer_incomplete",
    "agent_tool_error",
    "dataset_reference_noise",
    "endpoint_failure",
    "unsupported_specifics",
    "unknown",
}
SUGGESTED_LEVERS = {
    "scenario_prompt",
    "metric_config",
    "threshold",
    "dataset",
    "endpoint_template",
    "none",
}
SEVERITIES = {"low", "medium", "high"}


def parse_json_object(text: str) -> dict[str, Any]:
    value = (text or "").strip()
    if value.startswith("```"):
        value = re.sub(r"^```[a-zA-Z]*\s*", "", value)
        value = re.sub(r"\s*```$", "", value)
    start = value.find("{")
    end = value.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("模型输出中没有 JSON 对象")
    data = json.loads(value[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("模型输出的 JSON 不是对象")
    return data


async def call_json_llm(
    llm_config,
    system_prompt: str,
    user_prompt: str,
    *,
    temperature: float | None = None,
    max_tokens: int = 1800,
    timeout: int = 120,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Call an OpenAI-compatible model and return (json_object, usage)."""

    from openai import AsyncOpenAI

    client = AsyncOpenAI(
        base_url=llm_config.api_base_url,
        api_key=llm_config.api_key,
        timeout=timeout,
        max_retries=1,
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    response = await client.chat.completions.create(
        model=llm_config.model_name,
        messages=messages,
        temperature=llm_config.temperature if temperature is None else temperature,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content or "{}"
    usage_obj = getattr(response, "usage", None)
    usage = {
        "llm_calls": 1,
        "prompt_tokens": int(getattr(usage_obj, "prompt_tokens", 0) or 0),
        "completion_tokens": int(getattr(usage_obj, "completion_tokens", 0) or 0),
    }
    return parse_json_object(content), usage


def _infer_root_cause(error: str | None, reason: str | None, score: float | None) -> str:
    text = f"{error or ''} {reason or ''}".lower()
    if "缺少必需字段" in text or "missing" in text or "字段缺失" in text:
        return "missing_field"
    if "接口调用失败" in text or "endpoint" in text or "timeout" in text or "连接" in text:
        return "endpoint_failure"
    if "json" in text or "解析" in text or "无法评分" in text or "parse" in text:
        return "judge_misconfiguration"
    if "检索" in text or "上下文" in text or "context" in text:
        return "retrieval_gap"
    if "不完整" in text or "遗漏" in text or "缺少关键" in text:
        return "answer_incomplete"
    if "工具" in text or "tool" in text:
        return "agent_tool_error"
    if score is None:
        return "judge_misconfiguration"
    return "unknown"


def _suggested_lever(root_cause: str) -> str:
    return {
        "prompt_ambiguity": "scenario_prompt",
        "missing_field": "dataset",
        "judge_misconfiguration": "metric_config",
        "retrieval_gap": "none",
        "answer_incomplete": "scenario_prompt",
        "agent_tool_error": "none",
        "dataset_reference_noise": "dataset",
        "endpoint_failure": "endpoint_template",
        "unsupported_specifics": "scenario_prompt",
        "unknown": "none",
    }.get(root_cause, "none")


def _severity(fail_count: int, total: int) -> str:
    if total <= 0:
        return "low"
    ratio = fail_count / total
    if ratio >= 0.5:
        return "high"
    if ratio >= 0.2:
        return "medium"
    return "low"


def rule_clusters(
    rows: list[RowScore],
    thresholds: dict[str, float],
    metric_stats: dict[str, Any],
) -> list[dict[str, Any]]:
    """Deterministic failure clusters grouped by metric and inferred root cause."""

    total = len(rows)
    buckets: dict[tuple[str, str], dict[str, Any]] = {}

    for row in rows:
        if row.error:
            key = ("*", _infer_root_cause(row.error, None, None))
            bucket = buckets.setdefault(
                key,
                {
                    "label": f"评估执行错误：{row.error[:80]}",
                    "root_cause_type": key[1],
                    "affected_metric": "",
                    "evidence_row_ids": [],
                    "suggested_lever": _suggested_lever(key[1]),
                    "severity": "high",
                },
            )
            bucket["evidence_row_ids"].append(row.row_id)
            continue

        for metric, threshold in thresholds.items():
            score = row.scores.get(metric)
            if score is not None and float(score) >= float(threshold):
                continue
            root_cause = _infer_root_cause(None, row.reasons.get(metric), score)
            key = (metric, root_cause)
            bucket = buckets.setdefault(
                key,
                {
                    "label": f"指标 {metric} 出现低于参考阈值的样本",
                    "root_cause_type": root_cause,
                    "affected_metric": metric,
                    "evidence_row_ids": [],
                    "suggested_lever": _suggested_lever(root_cause),
                    "severity": "low",
                },
            )
            bucket["evidence_row_ids"].append(row.row_id)
            bucket["severity"] = _severity(len(bucket["evidence_row_ids"]), total)

    clusters = list(buckets.values())
    for cluster in clusters:
        cluster["evidence_row_ids"] = cluster["evidence_row_ids"][:20]
        cluster["size"] = len(cluster["evidence_row_ids"])
        stats = metric_stats.get(cluster["affected_metric"]) or {}
        cluster["metric_mean"] = stats.get("mean")
        cluster["metric_pass_rate"] = stats.get("pass_rate")
    clusters.sort(key=lambda item: (-int(item.get("size") or 0), item["affected_metric"]))
    return clusters[:8]


def _prompt_excerpt(snapshot_metric: dict[str, Any]) -> str:
    definition = snapshot_metric.get("metric_definition") or {}
    config = definition.get("config") or {}
    text = (
        snapshot_metric.get("prompt_override")
        or config.get("prompt")
        or config.get("definition")
        or ""
    )
    return str(text)[:800]


def build_diagnosis_payload(
    loop,
    rows: list[RowScore],
    thresholds: dict[str, float],
    metric_stats: dict[str, Any],
    snapshot: dict[str, Any],
    clusters: list[dict[str, Any]],
) -> dict[str, Any]:
    metrics_context = []
    for item in snapshot.get("metrics") or []:
        definition = item.get("metric_definition") or {}
        name = definition.get("name")
        if not name:
            continue
        stats = metric_stats.get(name) or {}
        metrics_context.append(
            {
                "metric": name,
                "display_name": definition.get("display_name") or name,
                "metric_type": definition.get("metric_type"),
                "pass_threshold": item.get("pass_threshold"),
                "mean": stats.get("mean"),
                "pass_rate": stats.get("pass_rate"),
                "current_prompt_excerpt": _prompt_excerpt(item),
            }
        )

    failed_rows = [row for row in rows if not reference_row_pass(row, thresholds)]
    samples = []
    for row in failed_rows[:20]:
        score_detail = {}
        for metric, threshold in thresholds.items():
            score = row.scores.get(metric)
            if score is None or float(score) < float(threshold):
                score_detail[metric] = {
                    "score": score,
                    "threshold": threshold,
                    "reason": (row.reasons.get(metric) or "")[:500],
                }
        samples.append(
            {
                "row_id": row.row_id,
                "row_index": row.row_index,
                "error": (row.error or "")[:500] or None,
                "scores": score_detail,
            }
        )

    return {
        "objective_mode": loop.objective_mode,
        "objective_metric": loop.objective_metric,
        "metric_count": len(metrics_context),
        "row_count": len(rows),
        "failed_count": len(failed_rows),
        "metrics": metrics_context,
        "samples": samples,
        "rule_clusters": clusters,
    }


def _normalize_llm_clusters(
    data: dict[str, Any],
    allowed_row_ids: set[int],
) -> list[dict[str, Any]]:
    clusters = data.get("clusters")
    if not isinstance(clusters, list):
        return []
    normalized = []
    for item in clusters[:8]:
        if not isinstance(item, dict):
            continue
        root_cause = str(item.get("root_cause_type") or "unknown")
        if root_cause not in ROOT_CAUSE_TYPES:
            root_cause = "unknown"
        lever = str(item.get("suggested_lever") or "none")
        if lever not in SUGGESTED_LEVERS:
            lever = "none"
        severity = str(item.get("severity") or "medium").lower()
        if severity not in SEVERITIES:
            severity = "medium"
        evidence = [
            int(row_id)
            for row_id in (item.get("evidence_row_ids") or [])
            if str(row_id).isdigit() and int(row_id) in allowed_row_ids
        ]
        if not evidence:
            continue
        normalized.append(
            {
                "label": str(item.get("label") or "未命名失败簇")[:200],
                "root_cause_type": root_cause,
                "affected_metric": str(item.get("affected_metric") or ""),
                "evidence_row_ids": evidence[:20],
                "suggested_lever": lever,
                "severity": severity,
                "size": len(evidence[:20]),
            }
        )
    return normalized


async def diagnose_failures(
    db,
    loop,
    rows: list[RowScore],
    metric_stats: dict[str, Any],
    snapshot: dict[str, Any],
    *,
    train_row_ids: set[int],
    reference_thresholds: dict[str, float],
    llm_config=None,
) -> dict[str, Any]:
    """Diagnose only train rows; never include holdout evidence."""

    train_rows = [row for row in rows if int(row.row_id) in train_row_ids]
    thresholds = {
        str(name): float(value) for name, value in (reference_thresholds or {}).items()
    }
    if not thresholds:
        thresholds = {
            str((item.get("metric_definition") or {}).get("name")): float(
                item.get("pass_threshold") if item.get("pass_threshold") is not None else 0.7
            )
            for item in snapshot.get("metrics") or []
            if (item.get("metric_definition") or {}).get("name")
        }
    clusters = rule_clusters(train_rows, thresholds, metric_stats)
    failed_count = sum(1 for row in train_rows if not reference_row_pass(row, thresholds))

    result: dict[str, Any] = {
        "summary": (
            f"规则归因：train 切片共 {len(train_rows)} 行，{failed_count} 行未通过参考阈值，"
            f"归纳为 {len(clusters)} 个失败簇。"
        ),
        "clusters": clusters,
        "sample_row_ids": [
            row.row_id for row in train_rows if not reference_row_pass(row, thresholds)
        ][:20],
        "fallback": True,
        "fallback_reason": "未配置归因 LLM",
        "train_rows": len(train_rows),
        "failed_rows": failed_count,
    }

    if llm_config is None or not getattr(llm_config, "api_key", None):
        return result
    if not failed_count:
        result["fallback_reason"] = "没有失败样本，跳过 LLM 归因"
        return result

    payload = build_diagnosis_payload(
        loop, train_rows, thresholds, metric_stats, snapshot, clusters
    )
    user_prompt = json.dumps(
        {
            "task": "归纳失败原因并输出 JSON",
            "output_schema": RSI_DIAGNOSIS_OUTPUT_SCHEMA,
            "context": payload,
        },
        ensure_ascii=False,
    )
    try:
        data, usage = await call_json_llm(
            llm_config,
            RSI_DIAGNOSIS_SYSTEM_PROMPT,
            user_prompt,
            max_tokens=1600,
        )
    except Exception as exc:
        result["fallback_reason"] = f"LLM 归因失败，已降级为规则归因: {str(exc)[:300]}"
        return result

    allowed = {int(item) for item in train_row_ids}
    llm_clusters = _normalize_llm_clusters(data, allowed)
    if not llm_clusters:
        result["fallback_reason"] = "LLM 归因未返回可用失败簇，已降级为规则归因"
        result["llm_usage"] = usage
        return result

    summary = str(data.get("summary") or "").strip()
    result.update(
        {
            "summary": summary[:2000] or result["summary"],
            "clusters": llm_clusters,
            "fallback": False,
            "fallback_reason": None,
            "llm_usage": usage,
        }
    )
    return result
