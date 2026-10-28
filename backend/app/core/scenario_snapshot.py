from __future__ import annotations

import copy
from types import SimpleNamespace
from typing import Any


def _metric_override_map(metric_overrides: list[Any] | None) -> dict[int, dict[str, Any]]:
    overrides: dict[int, dict[str, Any]] = {}
    for item in metric_overrides or []:
        if hasattr(item, "model_dump"):
            data = item.model_dump(exclude_unset=True)
        elif isinstance(item, dict):
            data = dict(item)
        else:
            data = {
                key: getattr(item, key)
                for key in ("metric_definition_id", "weight", "pass_threshold", "prompt_override")
                if hasattr(item, key)
            }
        metric_definition_id = data.get("metric_definition_id")
        if metric_definition_id is None:
            continue
        overrides[int(metric_definition_id)] = data
    return overrides


def build_scenario_snapshot(scenario, metric_overrides: list[Any] | None = None) -> dict[str, Any]:
    """Freeze the scenario config that a task should evaluate with."""

    overrides = _metric_override_map(metric_overrides)
    metrics = []
    for scenario_metric in sorted(scenario.metrics or [], key=lambda item: item.id or 0):
        metric_definition = scenario_metric.metric_definition
        if metric_definition is None:
            continue
        override = overrides.get(int(scenario_metric.metric_definition_id), {})
        metrics.append(
            {
                "id": scenario_metric.id,
                "metric_definition_id": scenario_metric.metric_definition_id,
                "weight": override.get("weight", scenario_metric.weight),
                "pass_threshold": (
                    override["pass_threshold"]
                    if "pass_threshold" in override
                    else scenario_metric.pass_threshold
                ),
                "prompt_override": (
                    override["prompt_override"]
                    if "prompt_override" in override
                    else getattr(scenario_metric, "prompt_override", None)
                ),
                "metric_definition": {
                    "id": metric_definition.id,
                    "name": metric_definition.name,
                    "display_name": metric_definition.display_name,
                    "metric_type": metric_definition.metric_type,
                    "config": metric_definition.config or {},
                    "category": metric_definition.category,
                    "is_builtin": metric_definition.is_builtin,
                },
            }
        )

    return {
        "id": scenario.id,
        "name": scenario.name,
        "description": scenario.description,
        "scene_type": scenario.scene_type,
        "sample_type": scenario.sample_type,
        "is_preset": scenario.is_preset,
        "metrics": metrics,
    }


def _find_snapshot_metric(snapshot: dict[str, Any], target_id: int) -> dict[str, Any] | None:
    """Locate a metric entry by ScenarioMetric id, falling back to definition id."""

    metrics = snapshot.get("metrics") or []
    for item in metrics:
        if item.get("id") == target_id:
            return item
    for item in metrics:
        if item.get("metric_definition_id") == target_id:
            return item
    return None


def build_candidate_snapshot(
    snapshot: dict[str, Any],
    patches: list[Any],
    *,
    loop_id: int | None = None,
    iteration_index: int | None = None,
) -> dict[str, Any]:
    """Deep-copy a frozen baseline snapshot and apply whitelisted patches.

    Only the fields explicitly listed here can be touched. The metric name set is
    preserved so baseline/candidate stay comparable, and an ``_rsi`` audit root
    key is added; ``snapshot_to_scenario_metrics`` only reads ``metrics`` so the
    extra key is ignored by the evaluation engine.
    """

    candidate = copy.deepcopy(snapshot or {})
    proposal_ids: list[int] = []

    for patch in patches:
        data = _patch_dict(patch)
        target_type = str(data.get("target_type") or "")
        field = str(data.get("field") or "")
        after_value = data.get("after_value")
        target_id = data.get("target_id")
        if data.get("proposal_id") is not None:
            proposal_ids.append(int(data["proposal_id"]))

        if target_type == "scenario_metric":
            item = _find_snapshot_metric(candidate, int(target_id)) if target_id is not None else None
            if item is None:
                raise ValueError(f"基线快照中找不到场景指标 {target_id}")
            if field in {"prompt_override", "pass_threshold", "weight"}:
                item[field] = copy.deepcopy(after_value)
            else:
                raise ValueError(f"不支持的场景指标字段: {field}")
        elif target_type == "metric_definition":
            definition_id = int(target_id) if target_id is not None else None
            entry = None
            for metric in candidate.get("metrics") or []:
                definition = metric.get("metric_definition") or {}
                if definition_id is not None and definition.get("id") == definition_id:
                    entry = definition
                    break
            if entry is None:
                raise ValueError(f"基线快照中找不到指标定义 {target_id}")
            if field.startswith("config."):
                config_key = field.split(".", 1)[1]
                config = dict(entry.get("config") or {})
                config[config_key] = copy.deepcopy(after_value)
                entry["config"] = config
            else:
                raise ValueError(f"不支持的指标定义字段: {field}")
        elif target_type == "scenario":
            if field != "description":
                raise ValueError(f"不支持的场景字段: {field}")
            candidate["description"] = copy.deepcopy(after_value)
        elif target_type == "endpoint_target":
            # Endpoint request templates live in EvalTask.target_config, not in
            # the scenario snapshot; the engine applies them to the shadow task.
            continue
        else:
            raise ValueError(f"不支持的 Patch 目标类型: {target_type}")

    candidate["_rsi"] = {
        "loop_id": loop_id,
        "iteration": iteration_index,
        "proposal_ids": proposal_ids,
    }
    return candidate


def _patch_dict(patch: Any) -> dict[str, Any]:
    if isinstance(patch, dict):
        return dict(patch)
    if hasattr(patch, "__dict__"):
        return {
            key: getattr(patch, key)
            for key in (
                "id",
                "target_type",
                "target_id",
                "field",
                "operation",
                "before_value",
                "after_value",
            )
            if hasattr(patch, key)
        } | ({"proposal_id": getattr(patch, "id", None)} if getattr(patch, "id", None) else {})
    return {}


def snapshot_to_scenario_metrics(snapshot: dict[str, Any] | None) -> list[Any]:
    """Hydrate frozen metric config into lightweight objects used by the engine."""

    if not snapshot:
        return []

    hydrated = []
    for item in snapshot.get("metrics") or []:
        metric_definition = item.get("metric_definition") or {}
        hydrated.append(
            SimpleNamespace(
                id=item.get("id"),
                scenario_id=snapshot.get("id"),
                metric_definition_id=item.get("metric_definition_id"),
                weight=item.get("weight", 1.0),
                pass_threshold=item.get("pass_threshold"),
                prompt_override=item.get("prompt_override"),
                metric_definition=SimpleNamespace(
                    id=metric_definition.get("id"),
                    name=metric_definition.get("name"),
                    display_name=metric_definition.get("display_name")
                    or metric_definition.get("name")
                    or "Unknown Metric",
                    metric_type=metric_definition.get("metric_type"),
                    config=metric_definition.get("config") or {},
                    category=metric_definition.get("category"),
                    is_builtin=metric_definition.get("is_builtin", False),
                ),
            )
        )
    return hydrated
