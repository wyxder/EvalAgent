"""LLM proposal generation for RSI.

The proposer only ever sees train-slice evidence and a compact configuration
view. Every proposal is structurally normalised and stripped of unsupported
fields before validation; the whitelist itself lives in ``rsi_patch``.
"""

from __future__ import annotations

import json
from typing import Any, Iterable

from app.core.config import settings
from app.core.prompt_manager import (
    RSI_PROPOSAL_OUTPUT_SCHEMA,
    RSI_PROPOSER_SYSTEM_PROMPT,
)
from app.core.rsi_diagnosis import call_json_llm


EDITABLE_FIELDS = [
    {
        "target_type": "scenario_metric",
        "field": "prompt_override",
        "phase": "mvp",
        "constraints": "仅本场景生效；≤4000 字符；不得包含密钥；强制人工审批",
    },
    {
        "target_type": "scenario_metric",
        "field": "pass_threshold",
        "phase": "mvp",
        "constraints": "0–1；单轮变化 ≤0.15；验收仍使用冻结参考阈值，强制人工审批",
    },
    {
        "target_type": "metric_definition",
        "field": "config.prompt",
        "phase": "p1",
        "constraints": "仅非内置指标；影响所有引用场景；≤4000 字符",
    },
    {
        "target_type": "metric_definition",
        "field": "config.definition",
        "phase": "p1",
        "constraints": "仅非内置指标；影响所有引用场景；≤4000 字符",
    },
    {
        "target_type": "metric_definition",
        "field": "config.description",
        "phase": "p1",
        "constraints": "仅非内置指标；影响所有引用场景；≤4000 字符",
    },
    {
        "target_type": "metric_definition",
        "field": "config.allowed_values",
        "phase": "p1",
        "constraints": "仅非内置指标；非空数组，≤50 个标量值",
    },
    {
        "target_type": "scenario",
        "field": "description",
        "phase": "p2",
        "constraints": "≤2000 字符；低风险，可配置自动采纳",
    },
    {
        "target_type": "endpoint_target",
        "field": "request_body_template",
        "phase": "p2",
        "constraints": "仅请求模板；不得出现 authorization/api_key/extra_headers；强制审批",
    },
]


def _metric_entries(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    entries = []
    for item in snapshot.get("metrics") or []:
        definition = item.get("metric_definition") or {}
        config = definition.get("config") or {}
        entries.append(
            {
                "scenario_metric_id": item.get("id"),
                "metric_definition_id": definition.get("id") or item.get("metric_definition_id"),
                "name": definition.get("name"),
                "display_name": definition.get("display_name"),
                "metric_type": definition.get("metric_type"),
                "is_builtin": bool(definition.get("is_builtin")),
                "pass_threshold": item.get("pass_threshold"),
                "weight": item.get("weight"),
                "prompt_override": item.get("prompt_override"),
                "config_prompt": str(config.get("prompt") or "")[:1200],
                "config_definition": str(config.get("definition") or "")[:1200],
                "allowed_values": config.get("allowed_values"),
            }
        )
    return entries


def build_proposal_context(
    loop,
    diagnosis: dict[str, Any],
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    metrics = _metric_entries(snapshot)
    metric_names = {entry["name"] for entry in metrics if entry.get("name")}
    evidence_rows = []
    for cluster in (diagnosis.get("clusters") or [])[:8]:
        evidence_rows.append(
            {
                "cluster": cluster.get("label"),
                "root_cause_type": cluster.get("root_cause_type"),
                "affected_metric": cluster.get("affected_metric"),
                "evidence_row_ids": [
                    row_id
                    for row_id in (cluster.get("evidence_row_ids") or [])
                    if row_id in (diagnosis.get("sample_row_ids") or [])
                ][:10],
                "severity": cluster.get("severity"),
                "suggested_lever": cluster.get("suggested_lever"),
                "metric_mean": cluster.get("metric_mean"),
            }
        )

    return {
        "loop": {
            "name": loop.name,
            "scenario_id": loop.scenario_id,
            "dataset_id": loop.dataset_id,
            "evaluation_mode": loop.evaluation_mode,
            "objective_mode": loop.objective_mode,
            "objective_metric": loop.objective_metric,
            "objective_target": loop.objective_target,
        },
        "metric_names": sorted(metric_names),
        "metrics": metrics,
        "diagnosis": {
            "summary": diagnosis.get("summary"),
            "fallback": diagnosis.get("fallback"),
            "failed_rows": diagnosis.get("failed_rows"),
            "train_rows": diagnosis.get("train_rows"),
            "clusters": evidence_rows,
        },
        "editable_fields": EDITABLE_FIELDS,
        "rules": [
            "每条提案只能修改一个字段，operation 必须为 set",
            "before_value 必须与给定配置完全一致",
            "必须提供 evidence.failed_row_ids 与 evidence.reason_snippets",
            "禁止修改 weight、metric_type、name、is_builtin、Judge 系统提示词",
            "禁止删除配置、写入 SQL/URL/密钥",
            "最多输出 3 条提案，优先风险低、证据强的方案",
        ],
    }


def _snapshot_lookup(
    payload: dict[str, Any],
    snapshot: dict[str, Any],
    loop,
) -> tuple[Any, Any]:
    """Return (target_id, before_value) resolved from the snapshot."""

    target_type = payload.get("target_type")
    field = payload.get("field")
    evidence_metric = str(((payload.get("evidence") or {}).get("metric")) or "")

    if target_type == "scenario_metric":
        for item in snapshot.get("metrics") or []:
            definition = item.get("metric_definition") or {}
            if evidence_metric and definition.get("name") != evidence_metric:
                continue
            return item.get("id") or item.get("metric_definition_id"), item.get(field)
        return None, None
    if target_type == "metric_definition":
        for item in snapshot.get("metrics") or []:
            definition = item.get("metric_definition") or {}
            if evidence_metric and definition.get("name") != evidence_metric:
                continue
            config = definition.get("config") or {}
            key = str(field or "").split(".", 1)[1] if str(field or "").startswith("config.") else None
            return definition.get("id"), config.get(key) if key else None
        return None, None
    if target_type == "scenario":
        return loop.scenario_id, snapshot.get("description")
    if target_type == "endpoint_target":
        return loop.endpoint_target_id, (loop.target_config or {}).get("request_body_template")
    return None, None


def _normalize_evidence(raw: Any, allowed_row_ids: set[int]) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    failed_row_ids: list[int] = []
    for value in raw.get("failed_row_ids") or []:
        try:
            row_id = int(value)
        except (TypeError, ValueError):
            continue
        if row_id in allowed_row_ids and row_id not in failed_row_ids:
            failed_row_ids.append(row_id)
    snippets = [
        str(item)[:500]
        for item in (raw.get("reason_snippets") or [])
        if str(item).strip()
    ][:6]
    if not failed_row_ids or not snippets:
        return None
    return {
        "metric": str(raw.get("metric") or "")[:100],
        "failed_row_ids": failed_row_ids[:20],
        "reason_snippets": snippets,
        "cluster": str(raw.get("cluster") or "")[:200],
    }


def normalize_proposal(
    raw: dict[str, Any],
    snapshot: dict[str, Any],
    loop,
    allowed_row_ids: set[int],
) -> tuple[dict[str, Any] | None, str | None]:
    """Normalise one LLM proposal; return (proposal, drop_reason)."""

    if not isinstance(raw, dict):
        return None, "提案不是对象"
    target_type = str(raw.get("target_type") or "")
    field = str(raw.get("field") or "")
    operation = str(raw.get("operation") or "set")
    evidence = _normalize_evidence(raw.get("evidence"), allowed_row_ids)
    if evidence is None:
        return None, "缺少有效的失败行证据或理由片段"

    resolved_target_id, resolved_before = _snapshot_lookup(raw, snapshot, loop)
    try:
        target_id = int(raw.get("target_id")) if raw.get("target_id") is not None else resolved_target_id
    except (TypeError, ValueError):
        target_id = resolved_target_id
    if target_id is None:
        return None, "无法定位 target_id"

    before_value = raw.get("before_value")
    if before_value is None:
        before_value = resolved_before
    after_value = raw.get("after_value")
    if isinstance(after_value, str) and field == "config.allowed_values":
        try:
            parsed = json.loads(after_value)
            if isinstance(parsed, list):
                after_value = parsed
        except (TypeError, ValueError, json.JSONDecodeError):
            return None, "allowed_values 必须是 JSON 数组"
    if after_value is None:
        return None, "after_value 为空"
    if isinstance(after_value, str) and len(after_value) > 8000:
        return None, "after_value 过长"

    rationale = str(raw.get("rationale") or "").strip()
    if not rationale:
        return None, "缺少 rationale"

    risk = str(raw.get("risk_level") or "medium").lower()
    if risk not in {"low", "medium", "high"}:
        risk = "medium"

    return {
        "target_type": target_type,
        "target_id": int(target_id),
        "field": field,
        "operation": operation,
        "before_value": before_value,
        "after_value": after_value,
        "rationale": rationale[:2000],
        "evidence": evidence,
        "risk_level": risk,
    }, None


def _proposal_key(payload: dict[str, Any]) -> str:
    return json.dumps(
        [
            payload.get("target_type"),
            payload.get("target_id"),
            payload.get("field"),
            payload.get("after_value"),
        ],
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )


async def generate_proposals(
    loop,
    diagnosis: dict[str, Any],
    snapshot: dict[str, Any],
    *,
    train_row_ids: Iterable[int],
    llm_config=None,
) -> dict[str, Any]:
    """Ask the proposer LLM for up to N whitelisted proposals."""

    result: dict[str, Any] = {
        "proposals": [],
        "raw_count": 0,
        "dropped": [],
        "error": None,
        "usage": {},
    }
    if llm_config is None or not getattr(llm_config, "api_key", None):
        result["error"] = "未配置提案 LLM"
        return result

    context = build_proposal_context(loop, diagnosis, snapshot)
    user_prompt = json.dumps(
        {
            "task": "基于失败归因生成配置优化提案",
            "output_schema": RSI_PROPOSAL_OUTPUT_SCHEMA,
            "context": context,
        },
        ensure_ascii=False,
    )
    try:
        data, usage = await call_json_llm(
            llm_config,
            RSI_PROPOSER_SYSTEM_PROMPT,
            user_prompt,
            temperature=settings.RSI_PROPOSER_TEMPERATURE,
            max_tokens=2600,
        )
    except Exception as exc:
        result["error"] = f"提案 LLM 调用失败: {str(exc)[:300]}"
        return result

    result["usage"] = usage
    raw_items = data.get("proposals")
    if not isinstance(raw_items, list):
        raw_items = data.get("items") if isinstance(data.get("items"), list) else []
    result["raw_count"] = len(raw_items)

    allowed = {int(item) for item in train_row_ids}
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in raw_items:
        payload, reason = normalize_proposal(raw, snapshot, loop, allowed)
        if payload is None:
            result["dropped"].append(reason)
            continue
        key = _proposal_key(payload)
        if key in seen:
            result["dropped"].append("同一轮重复提案")
            continue
        seen.add(key)
        normalized.append(payload)

    risk_order = {"low": 0, "medium": 1, "high": 2}
    normalized.sort(
        key=lambda item: (
            risk_order.get(item.get("risk_level"), 1),
            -len((item.get("evidence") or {}).get("failed_row_ids") or []),
        )
    )
    max_proposals = int((loop.budget or {}).get("max_proposals_per_iteration") or settings.RSI_MAX_PROPOSALS_PER_ITERATION)
    result["proposals"] = normalized[:max_proposals]
    if len(normalized) > max_proposals:
        result["dropped"].append(f"提案数量超过上限 {max_proposals}，已截断")
    return result


def create_proposal_rows(db, loop, iteration, payloads: list[dict[str, Any]]):
    """Persist normalised proposals before validation."""

    from app.models.rsi import RsiProposal

    rows = []
    for payload in payloads:
        row = RsiProposal(
            loop_id=loop.id,
            iteration_id=iteration.id,
            target_type=payload["target_type"],
            target_id=payload.get("target_id"),
            field=payload["field"],
            operation=payload.get("operation") or "set",
            before_value=payload.get("before_value"),
            after_value=payload.get("after_value"),
            rationale=payload.get("rationale"),
            evidence=payload.get("evidence"),
            risk_level=payload.get("risk_level") or "medium",
            requires_review=True,
            status="proposed",
        )
        db.add(row)
        rows.append(row)
    db.flush()
    return rows
