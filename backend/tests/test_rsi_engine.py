"""Engine tests: shadow-run orchestration, review gate, approval and rollback."""

import asyncio

from app.core import rsi_engine
from app.core.rsi_patch import rollback_iteration
from app.models.dataset import DatasetRow
from app.models.evaluation import EvalRowResult, EvalTask
from app.models.rsi import RsiConfigVersion, RsiIteration, RsiLoop, RsiProposal
from app.models.scenario import ScenarioMetric
from tests.conftest import TestingSessionLocal
from tests.rsi_helpers import add_loop, create_rsi_environment


def _make_shadow_completer(score: float):
    async def fake_shadow(task_id: int, session_factory=None):
        session = session_factory()
        try:
            task = session.query(EvalTask).filter(EvalTask.id == task_id).first()
            assert task is not None
            rows = (
                session.query(DatasetRow)
                .filter(DatasetRow.dataset_id == task.dataset_id)
                .order_by(DatasetRow.row_index)
                .all()
            )
            for row in rows:
                session.add(
                    EvalRowResult(
                        eval_task_id=task.id,
                        dataset_row_id=row.id,
                        row_index=row.row_index,
                        metric_scores={"faithfulness": score},
                        is_pass=score >= 0.7,
                    )
                )
            task.status = "completed"
            task.completed_rows = len(rows)
            session.commit()
        finally:
            session.close()

    return fake_shadow


def test_engine_waits_for_review_then_approve_and_rollback(db, monkeypatch):
    env = create_rsi_environment(db)
    loop = add_loop(db, env)

    async def fake_diagnosis(*args, **kwargs):
        return {
            "summary": "规则归因：1 个失败簇",
            "clusters": [
                {
                    "label": "低分",
                    "root_cause_type": "prompt_ambiguity",
                    "affected_metric": "faithfulness",
                    "evidence_row_ids": [env.rows[0].id],
                    "suggested_lever": "prompt_override",
                    "severity": "high",
                    "size": 1,
                }
            ],
            "fallback": True,
            "fallback_reason": "test",
            "train_rows": 6,
            "failed_rows": 6,
        }

    async def fake_proposals(loop, diagnosis, snapshot, *, train_row_ids, llm_config):
        return {
            "proposals": [
                {
                    "target_type": "scenario_metric",
                    "target_id": env.scenario_metric.id,
                    "field": "pass_threshold",
                    "operation": "set",
                    "before_value": 0.7,
                    "after_value": 0.6,
                    "rationale": "测试候选",
                    "evidence": {"failed_row_ids": [env.rows[0].id], "reason": "低分"},
                    "risk_level": "medium",
                    "requires_review": True,
                }
            ],
            "usage": {"llm_calls": 1},
        }

    monkeypatch.setattr(rsi_engine, "diagnose_failures", fake_diagnosis)
    monkeypatch.setattr(rsi_engine, "generate_proposals", fake_proposals)
    monkeypatch.setattr(rsi_engine, "run_shadow_evaluation", _make_shadow_completer(0.9))

    asyncio.run(rsi_engine.run_rsi_loop(loop.id, TestingSessionLocal))
    db.expire_all()

    loop = db.query(RsiLoop).filter(RsiLoop.id == loop.id).first()
    iteration = db.query(RsiIteration).filter(RsiIteration.loop_id == loop.id).one()
    proposal = db.query(RsiProposal).filter(RsiProposal.iteration_id == iteration.id).one()

    assert loop.status == "awaiting_review"
    assert iteration.status == "reviewing"
    assert proposal.status == "validated"
    assert iteration.metrics["decision_metrics"]["decision"] == "inconclusive"
    assert iteration.candidate_eval_id is not None

    rsi_engine.approve_iteration(db, iteration.id, actor="tester", resume=False)
    db.expire_all()

    loop = db.query(RsiLoop).filter(RsiLoop.id == loop.id).first()
    iteration = db.query(RsiIteration).filter(RsiIteration.id == iteration.id).first()
    proposal = db.query(RsiProposal).filter(RsiProposal.id == proposal.id).first()
    metric = (
        db.query(ScenarioMetric)
        .filter(ScenarioMetric.id == env.scenario_metric.id)
        .first()
    )

    assert loop.status == "completed"
    assert iteration.status == "accepted"
    assert proposal.status == "applied"
    assert metric.pass_threshold == 0.6
    assert (
        db.query(RsiConfigVersion)
        .filter(RsiConfigVersion.iteration_id == iteration.id)
        .count()
        == 1
    )

    rolled = rollback_iteration(db, iteration.id, actor="tester")
    db.commit()
    db.expire_all()

    metric = (
        db.query(ScenarioMetric)
        .filter(ScenarioMetric.id == env.scenario_metric.id)
        .first()
    )
    assert len(rolled) == 1
    assert metric.pass_threshold == 0.7


def test_engine_rejects_when_candidate_does_not_improve(db, monkeypatch):
    env = create_rsi_environment(db)
    loop = add_loop(db, env, budget={"max_iterations": 1})

    async def fake_diagnosis(*args, **kwargs):
        return {"summary": "no gains", "clusters": [], "fallback": True, "llm_usage": {}}

    async def fake_proposals(loop, diagnosis, snapshot, *, train_row_ids, llm_config):
        return {
            "proposals": [
                {
                    "target_type": "scenario_metric",
                    "target_id": env.scenario_metric.id,
                    "field": "pass_threshold",
                    "before_value": 0.7,
                    "after_value": 0.6,
                    "rationale": "noop",
                    "evidence": {"failed_row_ids": [env.rows[0].id], "reason": "低分"},
                }
            ],
            "usage": {},
        }

    monkeypatch.setattr(rsi_engine, "diagnose_failures", fake_diagnosis)
    monkeypatch.setattr(rsi_engine, "generate_proposals", fake_proposals)
    monkeypatch.setattr(rsi_engine, "run_shadow_evaluation", _make_shadow_completer(0.4))

    asyncio.run(rsi_engine.run_rsi_loop(loop.id, TestingSessionLocal))
    db.expire_all()

    loop = db.query(RsiLoop).filter(RsiLoop.id == loop.id).first()
    iteration = db.query(RsiIteration).filter(RsiIteration.loop_id == loop.id).one()

    assert iteration.status == "rejected"
    assert iteration.decision == "rejected"
    assert loop.status == "completed"
    assert loop.error_message is None


def test_cancel_loop_cancels_candidate_tasks(db):
    env = create_rsi_environment(db)
    loop = add_loop(db, env, status="running")
    task = EvalTask(
        name="[RSI] candidate",
        dataset_id=env.dataset.id,
        scenario_id=env.scenario.id,
        llm_config_id=env.llm.id,
        status="running",
        rsi_loop_id=loop.id,
    )
    db.add(task)
    db.commit()

    rsi_engine.cancel_loop(db, loop, actor="tester")
    db.refresh(loop)
    db.refresh(task)

    assert loop.status == "cancelled"
    assert task.status in {"cancelled"}
