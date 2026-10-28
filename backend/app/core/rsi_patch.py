"""Whitelisted configuration patches for RSI.

The proposer LLM may only produce structured patches. This module is the single
place that decides whether a patch is allowed, whether it drifted, how risky it
is, and how it is snapshotted, applied and rolled back.
"""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.core.evaluation_engine import diagnose_metric_prompt
from app.core.scenario_snapshot import build_candidate_snapshot, snapshot_to_scenario_metrics


SENSITIVE_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]{8,}", re.IGNORECASE),
]
TEMPLATE_FORBIDDEN_KEYS = ("authorization", "api_key", "extra_headers")
RISK_ORDER = {"low": 0, "medium": 1, "high": 2}


@dataclass(frozen=True)
class PatchSpec:
    phase: str
    risk: str
    value_type: str
    max_length: int | None = None
    min_value: float | None = None
    max_value: float | None = None
    max_delta: float | None = None
    force_review: bool = True


# Field-level whitelist. Anything not listed here is rejected outright.
PATCH_SPECS: dict[tuple[str, str], PatchSpec] = {
    ("scenario_metric", "prompt_override"): PatchSpec(
        phase="mvp", risk="medium", value_type="text", max_length=4000, force_review=True
    ),
    ("scenario_metric", "pass_threshold"): PatchSpec(
        phase="mvp",
        risk="medium",
        value_type="number",
        min_value=0.0,
        max_value=1.0,
        max_delta=0.15,
        force_review=True,
    ),
    ("metric_definition", "config.prompt"): PatchSpec(
        phase="p1", risk="medium", value_type="text", max_length=4000
    ),
    ("metric_definition", "config.definition"): PatchSpec(
        phase="p1", risk="medium", value_type="text", max_length=4000
    ),
    ("metric_definition", "config.description"): PatchSpec(
        phase="p1", risk="medium", value_type="text", max_length=4000
    ),
    ("metric_definition", "config.allowed_values"): PatchSpec(
        phase="p1", risk="medium", value_type="list"
    ),
    ("endpoint_target", "request_body_template"): PatchSpec(
        phase="p2", risk="high", value_type="text", max_length=4000, force_review=True
    ),
    ("scenario", "description"): PatchSpec(
        phase="p2", risk="low", value_type="text", max_length=2000, force_review=False
    ),
}

# All phases are implemented in this codebase; the flag documents the original
# staging and lets deployments narrow the surface later.
ENABLED_PHASES = {"mvp", "p1", "p2"}


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def canonical_value(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def values_equal(left: Any, right: Any) -> bool:
    if isinstance(left, (int, float)) and not isinstance(left, bool):
        if isinstance(right, (int, float)) and not isinstance(right, bool):
            return abs(float(left) - float(right)) <= 1e-9
    return left == right


def _find_snapshot_metric(snapshot: dict[str, Any], target_id: int) -> dict[str, Any] | None:
    for item in snapshot.get("metrics") or []:
        if item.get("id") == target_id:
            return item
    for item in snapshot.get("metrics") or []:
        if item.get("metric_definition_id") == target_id:
            return item
    return None


def _find_snapshot_definition(snapshot: dict[str, Any], definition_id: int) -> dict[str, Any] | None:
    for item in snapshot.get("metrics") or []:
        definition = item.get("metric_definition") or {}
        if definition.get("id") == definition_id:
            return definition
    return None


def _current_scenario_metric(db, loop, proposal):
    from app.models.scenario import ScenarioMetric

    target_id = _get(proposal, "target_id")
    if target_id is None:
        return None
    metric = db.query(ScenarioMetric).filter(ScenarioMetric.id == int(target_id)).first()
    if metric is None:
        return None
    if int(metric.scenario_id) != int(loop.scenario_id):
        return None
    return metric


def _current_metric_definition(db, proposal):
    from app.models.metric_definition import MetricDefinition

    target_id = _get(proposal, "target_id")
    if target_id is None:
        return None
    return (
        db.query(MetricDefinition)
        .filter(MetricDefinition.id == int(target_id))
        .first()
    )


def _current_scenario(db, loop, proposal):
    from app.models.scenario import EvalScenario

    target_id = _get(proposal, "target_id") or loop.scenario_id
    return (
        db.query(EvalScenario)
        .filter(EvalScenario.id == int(target_id))
        .first()
    )


def _current_endpoint_target(db, loop, proposal):
    from app.models.endpoint_target import EndpointTarget

    target_id = _get(proposal, "target_id") or loop.endpoint_target_id
    if target_id is None or loop.endpoint_target_id is None:
        return None
    if int(target_id) != int(loop.endpoint_target_id):
        return None
    return db.query(EndpointTarget).filter(EndpointTarget.id == int(target_id)).first()


def _baseline_value(loop, proposal, snapshot: dict[str, Any]) -> tuple[bool, Any]:
    """Return (found, value) from the frozen baseline snapshot / loop config."""

    target_type = _get(proposal, "target_type")
    field = _get(proposal, "field")
    target_id = _get(proposal, "target_id")

    if target_type == "scenario_metric":
        entry = _find_snapshot_metric(snapshot, int(target_id)) if target_id is not None else None
        if entry is None:
            return False, None
        return True, entry.get(field)
    if target_type == "metric_definition":
        entry = (
            _find_snapshot_definition(snapshot, int(target_id))
            if target_id is not None
            else None
        )
        if entry is None:
            return False, None
        if not str(field).startswith("config."):
            return False, None
        config_key = str(field).split(".", 1)[1]
        return True, (entry.get("config") or {}).get(config_key)
    if target_type == "scenario":
        target_id = target_id or loop.scenario_id
        if int(target_id) != int(loop.scenario_id):
            return False, None
        return True, snapshot.get("description")
    if target_type == "endpoint_target":
        target_id = target_id or loop.endpoint_target_id
        if target_id is None or loop.endpoint_target_id is None:
            return False, None
        if int(target_id) != int(loop.endpoint_target_id):
            return False, None
        return True, (loop.target_config or {}).get("request_body_template")
    return False, None


def _current_value(db, loop, proposal) -> tuple[bool, Any]:
    target_type = _get(proposal, "target_type")
    field = _get(proposal, "field")

    if target_type == "scenario_metric":
        metric = _current_scenario_metric(db, loop, proposal)
        if metric is None:
            return False, None
        return True, getattr(metric, field, None)
    if target_type == "metric_definition":
        definition = _current_metric_definition(db, proposal)
        if definition is None:
            return False, None
        if getattr(definition, "is_builtin", False):
            return False, None
        config_key = str(field).split(".", 1)[1] if str(field).startswith("config.") else None
        if config_key is None:
            return False, None
        return True, (definition.config or {}).get(config_key)
    if target_type == "scenario":
        scenario = _current_scenario(db, loop, proposal)
        if scenario is None:
            return False, None
        return True, getattr(scenario, "description", None)
    if target_type == "endpoint_target":
        target = _current_endpoint_target(db, loop, proposal)
        if target is None:
            return False, None
        return True, getattr(target, "request_body_template", None)
    return False, None


def _validate_value(spec: PatchSpec, value: Any, current: Any) -> list[str]:
    errors: list[str] = []
    if spec.value_type == "text":
        if not isinstance(value, str):
            return ["after_value 必须是字符串"]
        if not value.strip():
            return ["after_value 不能为空"]
        if spec.max_length is not None and len(value) > spec.max_length:
            errors.append(f"after_value 长度 {len(value)} 超过上限 {spec.max_length}")
        for pattern in SENSITIVE_PATTERNS:
            if pattern.search(value):
                errors.append("after_value 含有疑似凭据（sk-/Bearer），已拒绝")
                break
    elif spec.value_type == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return ["after_value 必须是数值"]
        numeric = float(value)
        if spec.min_value is not None and numeric < spec.min_value:
            errors.append(f"after_value 小于下限 {spec.min_value}")
        if spec.max_value is not None and numeric > spec.max_value:
            errors.append(f"after_value 大于上限 {spec.max_value}")
        if spec.max_delta is not None and isinstance(current, (int, float)):
            if abs(numeric - float(current)) > spec.max_delta + 1e-9:
                errors.append(f"单轮变化 {abs(numeric - float(current))} 超过 {spec.max_delta}")
    elif spec.value_type == "list":
        if not isinstance(value, list) or not value:
            return ["after_value 必须是非空数组"]
        if len(value) > 50:
            errors.append("allowed_values 元素过多（上限 50）")
        for item in value:
            if isinstance(item, (dict, list)):
                errors.append("allowed_values 只能包含字符串或数字")
                break
    return errors


def _representative_row_data(db, loop, proposal) -> dict[str, Any]:
    from app.models.dataset import DatasetRow

    evidence = _get(proposal, "evidence") or {}
    failed_ids = evidence.get("failed_row_ids") or []
    query = db.query(DatasetRow).filter(DatasetRow.dataset_id == loop.dataset_id)
    row = None
    if failed_ids:
        try:
            row = query.filter(DatasetRow.id == int(failed_ids[0])).first()
        except (TypeError, ValueError):
            row = None
    if row is None:
        row = query.order_by(DatasetRow.row_index).first()
    return dict(row.data or {}) if row is not None else {}


def _upgrade_risk(risk: str) -> str:
    index = min(RISK_ORDER.get(risk, 1) + 1, 2)
    return [name for name, order in RISK_ORDER.items() if order == index][0]


def _same_proposer_model(loop) -> bool:
    if loop.proposer_llm_config_id is None:
        return True
    return int(loop.proposer_llm_config_id) == int(loop.llm_config_id)


def _prompt_warnings(db, loop, proposal, after_value: Any, snapshot: dict[str, Any]) -> list[str]:
    """Run the existing static prompt checker against a representative row."""

    warnings: list[str] = []
    target_type = _get(proposal, "target_type")
    field = _get(proposal, "field")

    metric_definition_id = None
    prompt_override = None
    if target_type == "scenario_metric" and field == "prompt_override":
        entry = _find_snapshot_metric(snapshot, int(_get(proposal, "target_id")))
        if entry:
            metric_definition_id = entry.get("metric_definition_id")
            prompt_override = after_value
    elif target_type == "metric_definition" and field == "config.prompt":
        metric_definition_id = _get(proposal, "target_id")
    if metric_definition_id is None:
        return warnings

    hydrated = snapshot_to_scenario_metrics(snapshot)
    scenario_metric = next(
        (
            item
            for item in hydrated
            if int(item.metric_definition_id) == int(metric_definition_id)
        ),
        None,
    )
    if scenario_metric is None:
        return warnings

    definition = scenario_metric.metric_definition
    if target_type == "metric_definition" and field == "config.prompt":
        definition = copy.copy(definition)
        definition.config = {**(definition.config or {}), "prompt": after_value}
        prompt_override = getattr(scenario_metric, "prompt_override", None)
    elif target_type == "metric_definition":
        definition = copy.copy(definition)
        config_key = str(field).split(".", 1)[1]
        definition.config = {**(definition.config or {}), config_key: after_value}
        prompt_override = getattr(scenario_metric, "prompt_override", None)

    try:
        warnings = diagnose_metric_prompt(
            definition,
            _representative_row_data(db, loop, proposal),
            prompt_override=prompt_override,
            scenario_metric=scenario_metric,
            evaluation_mode=loop.evaluation_mode,
        )
    except Exception:
        warnings = ["无法完成 Prompt 静态校验，需人工复核"]
    return warnings


def validate_patch(db, loop, proposal, snapshot: dict[str, Any]) -> list[str]:
    """Validate one proposal; returns a list of human readable errors.

    Side effects on the ORM object: ``risk_level``, ``requires_review`` and
    ``evidence['validation_warnings']`` are updated when validation passes.
    Validation never writes the configuration.
    """

    errors: list[str] = []
    target_type = str(_get(proposal, "target_type") or "")
    field = str(_get(proposal, "field") or "")
    operation = str(_get(proposal, "operation") or "set")
    target_id = _get(proposal, "target_id")
    after_value = _get(proposal, "after_value")
    before_value = _get(proposal, "before_value")

    spec = PATCH_SPECS.get((target_type, field))
    if spec is None:
        return [f"字段不在白名单内: {target_type}.{field}"]
    if spec.phase not in ENABLED_PHASES:
        return [f"字段 {target_type}.{field} 属于 {spec.phase.upper()} 阶段，当前未启用"]
    if operation != "set":
        return [f"操作 {operation} 不被允许，MVP 仅允许 set"]

    if target_id is None:
        errors.append("target_id 不能为空")
    if target_type == "metric_definition" and field.startswith("config."):
        if field.split(".", 1)[1] not in {"prompt", "definition", "description", "allowed_values"}:
            errors.append(f"指标定义字段不在白名单内: {field}")

    found_baseline, baseline_value = _baseline_value(loop, proposal, snapshot)
    if not found_baseline:
        errors.append("基线快照中找不到对应的配置项，拒绝写入")
    found_current, current_value = _current_value(db, loop, proposal)
    if not found_current:
        errors.append("当前配置实体不存在或无权修改（内置指标/跨场景指标不可改）")

    if found_baseline and not values_equal(before_value, baseline_value):
        errors.append(
            "before_value 与基线快照不一致（配置已漂移）: "
            f"before={canonical_value(before_value)} baseline={canonical_value(baseline_value)}"
        )
    if found_current and not values_equal(before_value, current_value):
        errors.append(
            "before_value 与当前实体值不一致（配置已漂移）: "
            f"before={canonical_value(before_value)} current={canonical_value(current_value)}"
        )

    if not errors:
        errors.extend(_validate_value(spec, after_value, current_value))

    if target_type == "endpoint_target" and isinstance(after_value, str):
        lowered = after_value.lower()
        for key in TEMPLATE_FORBIDDEN_KEYS:
            if key in lowered:
                errors.append(f"请求模板不得包含敏感字段: {key}")
                break

    if values_equal(before_value, after_value):
        errors.append("after_value 与 before_value 相同，提案无实际变更")

    if errors:
        return errors

    risk = spec.risk
    if _same_proposer_model(loop):
        risk = _upgrade_risk(risk)
    warnings = _prompt_warnings(db, loop, proposal, after_value, snapshot)

    if hasattr(proposal, "risk_level"):
        proposal.risk_level = risk
    if hasattr(proposal, "requires_review"):
        proposal.requires_review = bool(spec.force_review or risk != "low" or not loop.auto_apply_low_risk)
    if hasattr(proposal, "evidence"):
        evidence = dict(proposal.evidence or {})
        evidence["validation_warnings"] = warnings
        evidence["baseline_value"] = baseline_value
        proposal.evidence = evidence

    # Dedupe across iterations of the same loop to avoid proposing forever.
    from app.models.rsi import RsiProposal

    prior = (
        db.query(RsiProposal)
        .filter(
            RsiProposal.loop_id == loop.id,
            RsiProposal.target_type == target_type,
            RsiProposal.field == field,
        )
        .all()
    )
    after_key = canonical_value(after_value)
    for item in prior:
        if item.id is not None and _get(proposal, "id") == item.id:
            continue
        if item.status in {"rejected", "failed", "rolled_back"}:
            continue
        if int(item.target_id or 0) != int(target_id or 0):
            continue
        if canonical_value(item.after_value) == after_key:
            return ["同一变更已在本 loop 中提案，拒绝重复提案"]
    return []


def build_candidate_snapshot_for_loop(
    loop,
    iteration,
    proposals: list[Any],
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    patches = []
    for proposal in proposals:
        patches.append(
            {
                "proposal_id": _get(proposal, "id"),
                "target_type": _get(proposal, "target_type"),
                "target_id": _get(proposal, "target_id"),
                "field": _get(proposal, "field"),
                "after_value": _get(proposal, "after_value"),
            }
        )
    return build_candidate_snapshot(
        snapshot,
        patches,
        loop_id=loop.id,
        iteration_index=_get(iteration, "iteration_index"),
    )


def candidate_endpoint_config(loop, proposals: list[Any]) -> dict[str, Any] | None:
    """Apply endpoint template patches to the frozen target config for shadow runs."""

    config = copy.deepcopy(loop.target_config or {})
    if not config:
        return None
    for proposal in proposals:
        if _get(proposal, "target_type") != "endpoint_target":
            continue
        if _get(proposal, "field") != "request_body_template":
            continue
        config["request_body_template"] = _get(proposal, "after_value")
    return config


def snapshot_before_apply(db, proposal) -> dict[str, Any]:
    target_type = _get(proposal, "target_type")
    if target_type == "scenario_metric":
        from app.models.scenario import ScenarioMetric

        metric = db.query(ScenarioMetric).filter(ScenarioMetric.id == int(_get(proposal, "target_id"))).first()
        if metric is None:
            raise ValueError("场景指标不存在")
        return {
            "weight": metric.weight,
            "pass_threshold": metric.pass_threshold,
            "prompt_override": metric.prompt_override,
        }
    if target_type == "metric_definition":
        from app.models.metric_definition import MetricDefinition

        definition = (
            db.query(MetricDefinition)
            .filter(MetricDefinition.id == int(_get(proposal, "target_id")))
            .first()
        )
        if definition is None:
            raise ValueError("指标定义不存在")
        return {"config": copy.deepcopy(definition.config or {})}
    if target_type == "scenario":
        from app.models.scenario import EvalScenario

        scenario = (
            db.query(EvalScenario)
            .filter(EvalScenario.id == int(_get(proposal, "target_id") or _current_loop_scenario(db, proposal)))
            .first()
        )
        if scenario is None:
            raise ValueError("场景不存在")
        return {"description": scenario.description}
    if target_type == "endpoint_target":
        from app.models.endpoint_target import EndpointTarget

        target = (
            db.query(EndpointTarget)
            .filter(EndpointTarget.id == int(_get(proposal, "target_id")))
            .first()
        )
        if target is None:
            raise ValueError("被测接口不存在")
        return {
            "endpoint_url": target.endpoint_url,
            "transport_mode": target.transport_mode,
            "authorization": target.authorization,
            "extra_headers": target.extra_headers,
            "request_body_template": target.request_body_template,
        }
    raise ValueError(f"不支持的 scope: {target_type}")


def _current_loop_scenario(db, proposal) -> int:
    from app.models.rsi import RsiLoop

    loop = db.query(RsiLoop).filter(RsiLoop.id == int(_get(proposal, "loop_id"))).first()
    return int(loop.scenario_id) if loop is not None else 0


def _next_version(db, scope: str, scope_id: int) -> int:
    from app.models.rsi import RsiConfigVersion

    current = (
        db.query(RsiConfigVersion.version)
        .filter(RsiConfigVersion.scope == scope, RsiConfigVersion.scope_id == scope_id)
        .order_by(RsiConfigVersion.version.desc())
        .first()
    )
    return (int(current[0]) if current else 0) + 1


def _parent_version_id(db, scope: str, scope_id: int) -> int | None:
    from app.models.rsi import RsiConfigVersion

    latest = (
        db.query(RsiConfigVersion)
        .filter(RsiConfigVersion.scope == scope, RsiConfigVersion.scope_id == scope_id)
        .order_by(RsiConfigVersion.version.desc())
        .first()
    )
    return latest.id if latest is not None else None


def _write_value(db, proposal, after_value: Any) -> None:
    target_type = _get(proposal, "target_type")
    field = _get(proposal, "field")
    if target_type == "scenario_metric":
        from app.models.scenario import ScenarioMetric

        metric = db.query(ScenarioMetric).filter(ScenarioMetric.id == int(_get(proposal, "target_id"))).first()
        if metric is None:
            raise ValueError("场景指标不存在")
        setattr(metric, field, after_value)
        return
    if target_type == "metric_definition":
        from app.models.metric_definition import MetricDefinition

        definition = (
            db.query(MetricDefinition)
            .filter(MetricDefinition.id == int(_get(proposal, "target_id")))
            .first()
        )
        if definition is None:
            raise ValueError("指标定义不存在")
        if definition.is_builtin:
            raise ValueError("内置指标不允许写入")
        config_key = str(field).split(".", 1)[1]
        config = dict(definition.config or {})
        config[config_key] = after_value
        definition.config = config
        return
    if target_type == "scenario":
        from app.models.scenario import EvalScenario

        scenario = (
            db.query(EvalScenario)
            .filter(EvalScenario.id == int(_get(proposal, "target_id")))
            .first()
        )
        if scenario is None:
            raise ValueError("场景不存在")
        scenario.description = after_value
        return
    if target_type == "endpoint_target":
        from app.models.endpoint_target import EndpointTarget

        target = (
            db.query(EndpointTarget)
            .filter(EndpointTarget.id == int(_get(proposal, "target_id")))
            .first()
        )
        if target is None:
            raise ValueError("被测接口不存在")
        target.request_body_template = after_value
        from app.models.rsi import RsiLoop

        loop = db.query(RsiLoop).filter(RsiLoop.id == int(_get(proposal, "loop_id"))).first()
        if loop is not None:
            config = dict(loop.target_config or {})
            config["request_body_template"] = after_value
            loop.target_config = config
        return
    raise ValueError(f"不支持的 Patch 目标: {target_type}")


def apply_patch(db, proposal, *, actor: str = "system", source: str = "manual"):
    """Snapshot first, then write the entity and mark the proposal applied."""

    from app.models.rsi import RsiConfigVersion

    scope = str(_get(proposal, "target_type"))
    scope_id = int(_get(proposal, "target_id"))
    snapshot = snapshot_before_apply(db, proposal)
    version = RsiConfigVersion(
        loop_id=_get(proposal, "loop_id"),
        iteration_id=_get(proposal, "iteration_id"),
        proposal_id=_get(proposal, "id"),
        scope=scope,
        scope_id=scope_id,
        version=_next_version(db, scope, scope_id),
        snapshot=snapshot,
        patch={
            "target_type": scope,
            "target_id": scope_id,
            "field": _get(proposal, "field"),
            "operation": "set",
            "before_value": _get(proposal, "before_value"),
            "after_value": _get(proposal, "after_value"),
        },
        parent_version_id=_parent_version_id(db, scope, scope_id),
        actor=actor,
    )
    db.add(version)
    db.flush()

    _write_value(db, proposal, _get(proposal, "after_value"))

    proposal.status = "applied"
    proposal.applied_version_id = version.id
    proposal.applied_at = datetime.now(timezone.utc)
    if proposal.decided_by is None:
        proposal.decided_by = actor
    proposal.decision_source = source
    db.flush()
    return version


def rollback_version(db, version_id: int, *, actor: str = "system") -> int:
    from app.models.rsi import RsiConfigVersion, RsiProposal

    version = db.query(RsiConfigVersion).filter(RsiConfigVersion.id == version_id).first()
    if version is None:
        raise ValueError("版本不存在")
    if version.rolled_back_at is not None:
        return version.id

    _restore_snapshot(db, version.scope, version.scope_id, version.snapshot)
    version.rolled_back_at = datetime.now(timezone.utc)
    if version.proposal_id:
        proposal = db.query(RsiProposal).filter(RsiProposal.id == version.proposal_id).first()
        if proposal is not None:
            proposal.status = "rolled_back"
            proposal.decided_by = proposal.decided_by or actor
            proposal.decided_at = proposal.decided_at or datetime.now(timezone.utc)
            proposal.decision_source = "manual"
    db.flush()
    return version.id


def rollback_iteration(db, iteration_id: int, *, actor: str = "system") -> list[int]:
    from app.models.rsi import RsiConfigVersion, RsiProposal

    versions = (
        db.query(RsiConfigVersion)
        .filter(RsiConfigVersion.iteration_id == iteration_id)
        .order_by(RsiConfigVersion.id.desc())
        .all()
    )
    rolled: list[int] = []
    for version in versions:
        rolled.append(rollback_version(db, version.id, actor=actor))
    proposals = (
        db.query(RsiProposal)
        .filter(RsiProposal.iteration_id == iteration_id)
        .all()
    )
    for proposal in proposals:
        if proposal.status == "applied":
            proposal.status = "rolled_back"
            proposal.decided_by = proposal.decided_by or actor
            proposal.decided_at = proposal.decided_at or datetime.now(timezone.utc)
    db.flush()
    return rolled


def _restore_snapshot(db, scope: str, scope_id: int, snapshot: dict[str, Any]) -> None:
    if scope == "scenario_metric":
        from app.models.scenario import ScenarioMetric

        metric = db.query(ScenarioMetric).filter(ScenarioMetric.id == scope_id).first()
        if metric is None:
            raise ValueError("场景指标不存在")
        for key in ("weight", "pass_threshold", "prompt_override"):
            if key in snapshot:
                setattr(metric, key, snapshot.get(key))
        return
    if scope == "metric_definition":
        from app.models.metric_definition import MetricDefinition

        definition = db.query(MetricDefinition).filter(MetricDefinition.id == scope_id).first()
        if definition is None:
            raise ValueError("指标定义不存在")
        definition.config = copy.deepcopy(snapshot.get("config") or {})
        return
    if scope == "scenario":
        from app.models.scenario import EvalScenario

        scenario = db.query(EvalScenario).filter(EvalScenario.id == scope_id).first()
        if scenario is None:
            raise ValueError("场景不存在")
        scenario.description = snapshot.get("description")
        return
    if scope == "endpoint_target":
        from app.models.endpoint_target import EndpointTarget

        target = db.query(EndpointTarget).filter(EndpointTarget.id == scope_id).first()
        if target is None:
            raise ValueError("被测接口不存在")
        for key in (
            "endpoint_url",
            "transport_mode",
            "authorization",
            "extra_headers",
            "request_body_template",
        ):
            if key in snapshot:
                setattr(target, key, snapshot.get(key))
        return
    raise ValueError(f"不支持的 scope: {scope}")


def restore_version(db, version_id: int, *, actor: str = "system"):
    """Append a new version that restores the given version's snapshot."""

    from app.models.rsi import RsiConfigVersion

    version = db.query(RsiConfigVersion).filter(RsiConfigVersion.id == version_id).first()
    if version is None:
        raise ValueError("版本不存在")
    current_snapshot = _current_snapshot(db, version.scope, version.scope_id)
    new_version = RsiConfigVersion(
        loop_id=version.loop_id,
        iteration_id=version.iteration_id,
        proposal_id=None,
        scope=version.scope,
        scope_id=version.scope_id,
        version=_next_version(db, version.scope, version.scope_id),
        snapshot=current_snapshot,
        patch={"restore_from": version.id},
        parent_version_id=_parent_version_id(db, version.scope, version.scope_id),
        actor=actor,
    )
    db.add(new_version)
    db.flush()
    _restore_snapshot(db, version.scope, version.scope_id, version.snapshot)
    db.flush()
    return new_version


def _current_snapshot(db, scope: str, scope_id: int) -> dict[str, Any]:
    if scope == "scenario_metric":
        from app.models.scenario import ScenarioMetric

        metric = db.query(ScenarioMetric).filter(ScenarioMetric.id == scope_id).first()
        if metric is None:
            raise ValueError("场景指标不存在")
        return {
            "weight": metric.weight,
            "pass_threshold": metric.pass_threshold,
            "prompt_override": metric.prompt_override,
        }
    if scope == "metric_definition":
        from app.models.metric_definition import MetricDefinition

        definition = db.query(MetricDefinition).filter(MetricDefinition.id == scope_id).first()
        if definition is None:
            raise ValueError("指标定义不存在")
        return {"config": copy.deepcopy(definition.config or {})}
    if scope == "scenario":
        from app.models.scenario import EvalScenario

        scenario = db.query(EvalScenario).filter(EvalScenario.id == scope_id).first()
        if scenario is None:
            raise ValueError("场景不存在")
        return {"description": scenario.description}
    if scope == "endpoint_target":
        from app.models.endpoint_target import EndpointTarget

        target = db.query(EndpointTarget).filter(EndpointTarget.id == scope_id).first()
        if target is None:
            raise ValueError("被测接口不存在")
        return {
            "endpoint_url": target.endpoint_url,
            "transport_mode": target.transport_mode,
            "authorization": target.authorization,
            "extra_headers": target.extra_headers,
            "request_body_template": target.request_body_template,
        }
    raise ValueError(f"不支持的 scope: {scope}")
