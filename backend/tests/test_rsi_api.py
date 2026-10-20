"""RSI API tests: create/list/detail/start guard/approve/reject/rollback/versions."""

from app.models.rsi import RsiConfigVersion, RsiIteration, RsiLoop, RsiProposal
from app.models.scenario import ScenarioMetric
from app.schemas.evaluation import EvalDebugResponse
from tests.rsi_helpers import add_loop, add_review_iteration, create_rsi_environment


def _create_loop_payload(env, **overrides):
    payload = {
        "name": "自进化循环",
        "baseline_eval_id": env.baseline.id,
        "llm_config_id": env.llm.id,
        "objective_metric": env.metric_name,
        "objective_mode": "reference_pass_rate",
        "budget": {"max_iterations": 2, "max_rows_per_iteration": 6},
        "acceptance_policy": {
            "objective": {"min_gain": 0.03},
            "sampling": {"holdout_ratio": 0.3, "min_rows": 5},
        },
        "auto_apply_low_risk": False,
    }
    payload.update(overrides)
    return payload


def test_create_loop_inherits_baseline_and_freezes_thresholds(client, db):
    env = create_rsi_environment(db)

    resp = client.post("/api/rsi/loops", json=_create_loop_payload(env))

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "draft"
    assert body["dataset_id"] == env.dataset.id
    assert body["scenario_id"] == env.scenario.id
    assert body["evaluation_mode"] == "offline"
    assert body["reference_thresholds"] == {env.metric_name: 0.7}
    assert body["budget"]["max_iterations"] == 2
    assert body["dataset_name"] == env.dataset.name
    assert body["scenario_name"] == env.scenario.name


def test_create_loop_rejects_unknown_objective_metric(client, db):
    env = create_rsi_environment(db)

    resp = client.post(
        "/api/rsi/loops",
        json=_create_loop_payload(env, objective_metric="not_a_metric"),
    )

    assert resp.status_code == 400
    assert "不在基线快照" in resp.json()["detail"]


def test_create_loop_rejects_unfinished_baseline(client, db):
    env = create_rsi_environment(db)
    env.baseline.status = "running"
    db.commit()

    resp = client.post("/api/rsi/loops", json=_create_loop_payload(env))

    assert resp.status_code == 400
    assert "尚未完成" in resp.json()["detail"]


def test_same_scenario_conflict_returns_409(client, db):
    env = create_rsi_environment(db)
    add_loop(db, env, status="running")

    resp = client.post("/api/rsi/loops", json=_create_loop_payload(env))

    assert resp.status_code == 409


def test_list_detail_and_logs(client, db):
    env = create_rsi_environment(db)
    loop = add_loop(db, env)
    loop.logs = "[00:00:00] hello\n"
    db.commit()

    listing = client.get("/api/rsi/loops")
    assert listing.status_code == 200
    assert listing.json()["total"] == 1

    detail = client.get(f"/api/rsi/loops/{loop.id}")
    assert detail.status_code == 200
    assert detail.json()["id"] == loop.id

    logs = client.get(f"/api/rsi/loops/{loop.id}/logs?offset=0")
    assert logs.status_code == 200
    assert logs.json()["logs"].startswith("[00:00:00]")

    missing = client.get("/api/rsi/loops/999999")
    assert missing.status_code == 404


def test_start_guard_rejects_running_loop(client, db, monkeypatch):
    env = create_rsi_environment(db)
    loop = add_loop(db, env, status="running")

    resp = client.post(f"/api/rsi/loops/{loop.id}/start")

    assert resp.status_code == 409

    draft = add_loop(db, env, status="draft")
    called = []
    monkeypatch.setattr("app.api.rsi.launch_rsi_loop", lambda loop_id: called.append(loop_id))
    resp = client.post(f"/api/rsi/loops/{draft.id}/start")
    assert resp.status_code == 200
    assert called == [draft.id]


def test_approve_writes_versions_and_rollback_restores(client, db):
    env = create_rsi_environment(db)
    loop = add_loop(db, env)
    iteration, proposal = add_review_iteration(db, env, loop, after_value=0.6)

    resp = client.post(
        f"/api/rsi/iterations/{iteration.id}/approve",
        json={"actor": "tester", "resume": False},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "accepted"
    assert body["decision"] == "accepted"
    db.refresh(env.scenario_metric)
    assert env.scenario_metric.pass_threshold == 0.6
    db.refresh(loop)
    assert loop.status == "completed"
    assert loop.best_iteration_id == iteration.id

    versions = client.get(
        f"/api/rsi/configs/scenario_metric/{env.scenario_metric.id}/versions"
    )
    assert versions.status_code == 200
    assert versions.json()["total"] == 1
    version_id = versions.json()["items"][0]["id"]

    rolled = client.post(
        f"/api/rsi/loops/{loop.id}/rollback",
        json={"iteration_id": iteration.id, "actor": "tester"},
    )
    assert rolled.status_code == 200, rolled.text
    assert version_id in rolled.json()["rolled_back_version_ids"]
    db.refresh(env.scenario_metric)
    assert env.scenario_metric.pass_threshold == 0.7
    db.refresh(iteration)
    assert iteration.status == "rolled_back"


def test_approve_rejects_drifted_configuration(client, db):
    env = create_rsi_environment(db)
    loop = add_loop(db, env)
    iteration, proposal = add_review_iteration(db, env, loop, after_value=0.6)
    env.scenario_metric.pass_threshold = 0.8
    db.commit()

    resp = client.post(
        f"/api/rsi/iterations/{iteration.id}/approve",
        json={"actor": "tester", "resume": False},
    )

    assert resp.status_code == 422
    assert "漂移" in resp.json()["detail"]
    db.refresh(env.scenario_metric)
    assert env.scenario_metric.pass_threshold == 0.8


def test_reject_marks_proposals_and_stops_loop(client, db):
    env = create_rsi_environment(db)
    loop = add_loop(db, env)
    iteration, proposal = add_review_iteration(db, env, loop, after_value=0.6)

    resp = client.post(
        f"/api/rsi/iterations/{iteration.id}/reject",
        json={"reason": "方案风险过高", "resume": False},
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "rejected"
    db.refresh(proposal)
    assert proposal.status == "rejected"
    db.refresh(loop)
    assert loop.status == "completed"
    db.refresh(env.scenario_metric)
    assert env.scenario_metric.pass_threshold == 0.7


def test_approve_requires_review_state(client, db):
    env = create_rsi_environment(db)
    loop = add_loop(db, env)
    iteration = RsiIteration(
        loop_id=loop.id,
        iteration_index=1,
        status="rejected",
        baseline_eval_id=env.baseline.id,
    )
    db.add(iteration)
    db.commit()

    resp = client.post(f"/api/rsi/iterations/{iteration.id}/approve", json={})
    assert resp.status_code == 422


def test_restore_version_endpoint(client, db):
    env = create_rsi_environment(db)
    loop = add_loop(db, env)
    iteration, proposal = add_review_iteration(db, env, loop, after_value=0.6)
    approve = client.post(
        f"/api/rsi/iterations/{iteration.id}/approve",
        json={"resume": False},
    )
    assert approve.status_code == 200, approve.text
    version_id = (
        db.query(RsiConfigVersion)
        .filter(RsiConfigVersion.scope == "scenario_metric")
        .one()
        .id
    )

    restore = client.post(f"/api/rsi/configs/versions/{version_id}/restore")
    assert restore.status_code == 200, restore.text
    assert restore.json()["version"] == 2
    db.refresh(env.scenario_metric)
    assert env.scenario_metric.pass_threshold == 0.7


def test_preview_proposal_uses_candidate_snapshot(client, db, monkeypatch):
    env = create_rsi_environment(db)
    loop = add_loop(db, env)
    iteration, proposal = add_review_iteration(db, env, loop, after_value=0.6)
    captured = {}

    async def fake_debug(db_session, payload, *, scenario_snapshot=None):
        captured["snapshot"] = scenario_snapshot
        captured["row_id"] = payload.row_id
        return EvalDebugResponse(
            success=True,
            message="ok",
            metric_scores={env.metric_name: {"score": 0.9, "reason": "good"}},
            is_pass=True,
        )

    monkeypatch.setattr("app.api.rsi.run_debug_evaluation", fake_debug)
    resp = client.post(
        f"/api/rsi/proposals/{proposal.id}/preview",
        json={"row_id": env.rows[0].id},
    )

    assert resp.status_code == 200, resp.text
    assert captured["snapshot"]["metrics"][0]["pass_threshold"] == 0.6
    assert captured["row_id"] == env.rows[0].id
    assert resp.json()["is_pass"] is True


def test_hard_case_dataset_is_append_only(client, db):
    env = create_rsi_environment(db)
    loop = add_loop(db, env)

    resp = client.post(
        f"/api/rsi/loops/{loop.id}/hard-cases",
        json={"row_ids": [env.rows[0].id], "name": "hard cases"},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["created_rows"] == 1
    assert env.dataset.row_count == 6


def test_compare_returns_threshold_independent_slices(client, db):
    env = create_rsi_environment(db)
    loop = add_loop(db, env)
    iteration, proposal = add_review_iteration(db, env, loop, after_value=0.6)

    resp = client.get(f"/api/rsi/loops/{loop.id}/compare?iteration_id={iteration.id}")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["iteration_id"] == iteration.id
    assert body["objective_mode"] == "reference_pass_rate"
    assert body["full"]["baseline"] == {}
    assert body["train"] == {}


def test_rsi_disabled_returns_403(client, db, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "RSI_ENABLED", False)
    resp = client.get("/api/rsi/loops")
    assert resp.status_code == 403
