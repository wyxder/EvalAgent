"""Dedicated tests for RSI configuration versioning, immutability, field-level rollback, and lineage."""

import pytest
from app.core.rsi_patch import (
    apply_patch,
    restore_version,
    rollback_iteration,
    rollback_version,
)
from app.models.rsi import RsiConfigVersion
from tests.rsi_helpers import add_loop, add_review_iteration, create_rsi_environment


def test_version_records_are_append_only_and_increment(db):
    """Ensure versions increment monotonically and old versions are not overwritten."""
    env = create_rsi_environment(db)
    loop = add_loop(db, env)
    iter1, prop1 = add_review_iteration(db, env, loop, after_value=0.6)

    v1 = apply_patch(db, prop1, actor="user-1")
    db.commit()

    assert v1.version == 1
    assert v1.scope == "scenario_metric"
    assert v1.scope_id == env.scenario_metric.id
    assert v1.snapshot["pass_threshold"] == 0.7
    assert v1.patch["after_value"] == 0.6

    # Apply a second patch with incremented current_iteration
    loop.current_iteration = 1
    db.commit()
    iter2, prop2 = add_review_iteration(db, env, loop, after_value=0.55, before_value=0.6)
    v2 = apply_patch(db, prop2, actor="user-2")
    db.commit()

    assert v2.version == 2
    assert v2.parent_version_id == v1.id
    assert v2.snapshot["pass_threshold"] == 0.6
    assert v2.patch["after_value"] == 0.55

    # Check total count in DB
    versions = (
        db.query(RsiConfigVersion)
        .filter(
            RsiConfigVersion.scope == "scenario_metric",
            RsiConfigVersion.scope_id == env.scenario_metric.id,
        )
        .order_by(RsiConfigVersion.version.asc())
        .all()
    )
    assert len(versions) == 2
    assert versions[0].id == v1.id
    assert versions[1].id == v2.id


def test_rollback_version_restores_exact_snapshot_fields(db):
    """Ensure rolling back restores the entity field values to match snapshot exactly."""
    env = create_rsi_environment(db)
    loop = add_loop(db, env)
    iteration, proposal = add_review_iteration(db, env, loop, after_value=0.5)

    initial_threshold = env.scenario_metric.pass_threshold
    initial_prompt = env.scenario_metric.prompt_override

    version = apply_patch(db, proposal, actor="tester")
    db.commit()
    db.refresh(env.scenario_metric)

    assert env.scenario_metric.pass_threshold == 0.5

    # Perform rollback
    rolled_id = rollback_version(db, version.id, actor="operator")
    db.commit()
    db.refresh(env.scenario_metric)

    assert rolled_id == version.id
    assert env.scenario_metric.pass_threshold == initial_threshold
    assert env.scenario_metric.prompt_override == initial_prompt
    assert version.rolled_back_at is not None
    assert proposal.status == "rolled_back"


def test_restore_version_creates_new_version_with_lineage(db):
    """Ensure restore_version appends a new version referencing the restored version."""
    env = create_rsi_environment(db)
    loop = add_loop(db, env)
    iteration, proposal = add_review_iteration(db, env, loop, after_value=0.5)

    v1 = apply_patch(db, proposal, actor="tester")
    db.commit()

    restored = restore_version(db, v1.id, actor="admin")
    db.commit()
    db.refresh(env.scenario_metric)

    assert restored.version == 2
    assert restored.parent_version_id == v1.id
    assert restored.patch["restore_from"] == v1.id
    assert env.scenario_metric.pass_threshold == 0.7


def test_rollback_iteration_reverts_all_iteration_proposals(db):
    """Ensure rollback_iteration rolls back all applied proposals belonging to the iteration."""
    env = create_rsi_environment(db)
    loop = add_loop(db, env)
    iteration, proposal = add_review_iteration(db, env, loop, after_value=0.5)

    version = apply_patch(db, proposal, actor="tester")
    db.commit()
    db.refresh(env.scenario_metric)
    assert env.scenario_metric.pass_threshold == 0.5

    rolled_versions = rollback_iteration(db, iteration.id, actor="approver")
    db.commit()
    db.refresh(env.scenario_metric)

    assert version.id in rolled_versions
    assert env.scenario_metric.pass_threshold == 0.7
    assert proposal.status == "rolled_back"


def test_rollback_invalid_version_raises_error(db):
    """Ensure rollback handles missing versions with ValueError."""
    with pytest.raises(ValueError, match="不存在"):
        rollback_version(db, 999999)

    env = create_rsi_environment(db)
    loop = add_loop(db, env)
    iteration, proposal = add_review_iteration(db, env, loop, after_value=0.5)
    v = apply_patch(db, proposal)
    db.commit()

    # First rollback succeeds
    rolled = rollback_version(db, v.id)
    assert rolled == v.id

    # Second rollback is idempotent and returns version.id
    rolled_again = rollback_version(db, v.id)
    assert rolled_again == v.id
