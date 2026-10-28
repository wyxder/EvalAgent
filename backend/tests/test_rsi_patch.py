"""Whitelist, drift, snapshot, write-back and rollback tests."""

from types import SimpleNamespace

import pytest

from app.core.rsi_patch import (
    apply_patch,
    build_candidate_snapshot_for_loop,
    restore_version,
    rollback_version,
    validate_patch,
)
from app.models.rsi import RsiConfigVersion
from tests.rsi_helpers import add_loop, add_review_iteration, create_rsi_environment


def _proposal(**overrides):
    fields = {
        "id": 1,
        "loop_id": 1,
        "iteration_id": 1,
        "target_type": "scenario_metric",
        "target_id": 1,
        "field": "pass_threshold",
        "operation": "set",
        "before_value": 0.7,
        "after_value": 0.6,
        "rationale": "测试",
        "evidence": {"failed_row_ids": [1], "reason": "低分"},
        "risk_level": "medium",
        "requires_review": True,
        "status": "proposed",
    }
    fields.update(overrides)
    return SimpleNamespace(**fields)


def _loop(env, **overrides):
    fields = {
        "id": 999,
        "scenario_id": env.scenario.id,
        "dataset_id": env.dataset.id,
        "llm_config_id": env.llm.id,
        "proposer_llm_config_id": None,
        "evaluation_mode": "offline",
        "endpoint_target_id": None,
        "target_config": None,
        "auto_apply_low_risk": False,
    }
    fields.update(overrides)
    return SimpleNamespace(**fields)


@pytest.mark.parametrize(
    "target_type,field,after,before",
    [
        ("scenario_metric", "pass_threshold", 0.6, 0.7),
        ("scenario_metric", "prompt_override", "新的提示词", None),
        ("metric_definition", "config.prompt", "新的指标提示词", None),
        ("metric_definition", "config.description", "新的描述", None),
        ("metric_definition", "config.allowed_values", ["yes", "no"], [0, 1]),
    ],
)
def test_whitelisted_patches_pass_validation(db, target_type, field, after, before):
    env = create_rsi_environment(db)
    loop = _loop(env)
    target_id = env.scenario_metric.id if target_type == "scenario_metric" else env.definition.id
    proposal = _proposal(
        target_type=target_type,
        target_id=target_id,
        field=field,
        after_value=after,
        before_value=before,
    )

    errors = validate_patch(db, loop, proposal, env.snapshot)

    assert errors == [], errors


def test_unlisted_field_is_rejected(db):
    env = create_rsi_environment(db)
    proposal = _proposal(field="weight", after_value=0.5)

    errors = validate_patch(db, _loop(env), proposal, env.snapshot)

    assert any("白名单" in item for item in errors)


def test_before_value_drift_against_snapshot_is_rejected(db):
    env = create_rsi_environment(db)
    proposal = _proposal(before_value=0.65, after_value=0.55)

    errors = validate_patch(db, _loop(env), proposal, env.snapshot)

    assert any("基线快照" in item for item in errors)


def test_before_value_drift_against_live_entity_is_rejected(db):
    env = create_rsi_environment(db)
    env.scenario_metric.pass_threshold = 0.8
    db.commit()
    proposal = _proposal(before_value=0.7, after_value=0.6)

    errors = validate_patch(db, _loop(env), proposal, env.snapshot)

    assert any("当前实体值" in item for item in errors)


def test_sensitive_string_and_delta_limits_are_rejected(db):
    env = create_rsi_environment(db)
    loop = _loop(env)

    sensitive = _proposal(
        field="prompt_override",
        after_value="please use sk-abcdefgh12345678",
        before_value=None,
    )
    errors = validate_patch(db, loop, sensitive, env.snapshot)
    assert any("凭据" in item for item in errors)

    too_large = _proposal(before_value=0.7, after_value=0.95)
    errors = validate_patch(db, loop, too_large, env.snapshot)
    assert any("单轮变化" in item for item in errors)


def test_identical_value_is_rejected(db):
    env = create_rsi_environment(db)
    proposal = _proposal(before_value=0.7, after_value=0.7)

    errors = validate_patch(db, _loop(env), proposal, env.snapshot)

    assert any("相同" in item for item in errors)


def test_candidate_snapshot_does_not_mutate_baseline(db):
    env = create_rsi_environment(db)
    loop = add_loop(db, env)
    iteration, proposal = add_review_iteration(db, env, loop, after_value=0.5)

    candidate = build_candidate_snapshot_for_loop(
        loop, iteration, [proposal], env.snapshot
    )

    assert candidate["metrics"][0]["pass_threshold"] == 0.5
    assert env.snapshot["metrics"][0]["pass_threshold"] == 0.7
    assert candidate["_rsi"]["loop_id"] == loop.id
    assert candidate["_rsi"]["iteration"] == iteration.iteration_index


def test_apply_snapshots_then_writes_and_rollback_restores(db):
    env = create_rsi_environment(db)
    loop = add_loop(db, env)
    iteration, proposal = add_review_iteration(db, env, loop, after_value=0.5)

    version = apply_patch(db, proposal, actor="tester", source="manual")
    db.commit()
    db.refresh(env.scenario_metric)

    assert env.scenario_metric.pass_threshold == 0.5
    assert version.scope == "scenario_metric"
    assert version.scope_id == env.scenario_metric.id
    assert version.snapshot["pass_threshold"] == 0.7
    assert version.patch["after_value"] == 0.5
    assert proposal.status == "applied"
    assert proposal.applied_version_id == version.id

    rolled = rollback_version(db, version.id, actor="tester")
    db.commit()
    db.refresh(env.scenario_metric)

    assert rolled == version.id
    assert env.scenario_metric.pass_threshold == 0.7
    assert version.rolled_back_at is not None
    assert proposal.status == "rolled_back"


def test_restore_version_appends_a_new_version(db):
    env = create_rsi_environment(db)
    loop = add_loop(db, env)
    iteration, proposal = add_review_iteration(db, env, loop, after_value=0.5)

    version = apply_patch(db, proposal, actor="tester")
    db.commit()
    restored = restore_version(db, version.id, actor="tester")
    db.commit()
    db.refresh(env.scenario_metric)

    assert env.scenario_metric.pass_threshold == 0.7
    assert restored.version == version.version + 1
    assert restored.snapshot["pass_threshold"] == 0.5
    assert restored.patch["restore_from"] == version.id
    assert (
        db.query(RsiConfigVersion)
        .filter(RsiConfigVersion.scope == "scenario_metric")
        .count()
        == 2
    )
