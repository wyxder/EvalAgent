"""Shared fixtures for the RSI test modules (not a pytest test module)."""

from __future__ import annotations

from types import SimpleNamespace

from app.core.rsi_patch import PATCH_SPECS
from app.core.scenario_snapshot import build_scenario_snapshot
from app.models.dataset import Dataset, DatasetRow
from app.models.evaluation import EvalRowResult, EvalTask
from app.models.llm_config import LLMConfig
from app.models.metric_definition import MetricDefinition
from app.models.rsi import RsiIteration, RsiLoop, RsiProposal
from app.models.scenario import EvalScenario, ScenarioMetric


def create_rsi_environment(
    db,
    *,
    metric_name: str = "faithfulness",
    threshold: float = 0.7,
    row_count: int = 6,
    baseline_score: float = 0.4,
):
    """Create LLM config, metric, scenario, dataset, baseline eval and rows."""

    llm = LLMConfig(
        name="RSI Judge",
        provider="openai",
        api_base_url="https://api.example.com/v1",
        api_key="test-api-key",
        model_name="test-model",
    )
    db.add(llm)
    db.flush()

    definition = MetricDefinition(
        name=metric_name,
        display_name="忠实度",
        metric_type="numeric",
        config={"definition": "回答是否忠实于上下文", "allowed_values": [0, 1]},
        category="custom",
        is_builtin=False,
    )
    db.add(definition)
    db.flush()

    scenario = EvalScenario(
        name="RSI Scenario",
        description="baseline description",
        scene_type="rag",
        sample_type="single_turn",
    )
    db.add(scenario)
    db.flush()

    scenario_metric = ScenarioMetric(
        scenario_id=scenario.id,
        metric_definition_id=definition.id,
        weight=1.0,
        pass_threshold=threshold,
    )
    db.add(scenario_metric)
    db.flush()

    dataset = Dataset(
        name="RSI Dataset",
        description="rsi test dataset",
        sample_type="single_turn",
        field_schema=[
            {"name": "user_input", "type": "text", "required": True, "description": ""},
            {"name": "response", "type": "text", "required": False, "description": ""},
        ],
        row_count=row_count,
    )
    db.add(dataset)
    db.flush()

    rows = []
    for index in range(row_count):
        row = DatasetRow(
            dataset_id=dataset.id,
            row_index=index,
            data={"user_input": f"question {index}", "response": f"answer {index}"},
        )
        db.add(row)
        rows.append(row)
    db.flush()

    db.refresh(scenario)
    snapshot = build_scenario_snapshot(scenario)

    baseline = EvalTask(
        name="Baseline Eval",
        dataset_id=dataset.id,
        scenario_id=scenario.id,
        llm_config_id=llm.id,
        status="completed",
        total_rows=row_count,
        completed_rows=row_count,
        summary_scores={metric_name: {"mean": baseline_score}},
        scenario_snapshot=snapshot,
    )
    db.add(baseline)
    db.flush()
    for row in rows:
        db.add(
            EvalRowResult(
                eval_task_id=baseline.id,
                dataset_row_id=row.id,
                row_index=row.row_index,
                metric_scores={metric_name: baseline_score},
                is_pass=False,
            )
        )
    db.commit()
    for item in (llm, definition, scenario, scenario_metric, dataset, baseline, *rows):
        db.refresh(item)

    return SimpleNamespace(
        llm=llm,
        definition=definition,
        scenario=scenario,
        scenario_metric=scenario_metric,
        dataset=dataset,
        rows=rows,
        baseline=baseline,
        snapshot=snapshot,
        metric_name=metric_name,
    )


def add_loop(db, env, **overrides) -> RsiLoop:
    fields = {
        "name": "RSI Loop",
        "status": "draft",
        "baseline_eval_id": env.baseline.id,
        "dataset_id": env.dataset.id,
        "scenario_id": env.scenario.id,
        "llm_config_id": env.llm.id,
        "evaluation_mode": "offline",
        "result_save_mode": "task_only",
        "objective_metric": env.metric_name,
        "objective_mode": "reference_pass_rate",
        "reference_thresholds": {env.metric_name: env.scenario_metric.pass_threshold or 0.7},
        "holdout_config": {"holdout_ratio": 0, "min_rows": 5, "min_rows_for_auto_accept": 5},
        "acceptance_policy": None,
        "budget": {"max_iterations": 2},
        "usage": {"llm_calls": 0, "consecutive_no_gain": 0},
        "current_iteration": 0,
        "auto_apply_low_risk": False,
        "logs": "",
    }
    fields.update(overrides)
    loop = RsiLoop(**fields)
    db.add(loop)
    db.commit()
    db.refresh(loop)
    return loop


def add_review_iteration(
    db,
    env,
    loop: RsiLoop,
    *,
    field: str = "pass_threshold",
    after_value=0.5,
    before_value=None,
    decision: str = "inconclusive",
) -> tuple[RsiIteration, RsiProposal]:
    if before_value is None:
        before_value = env.scenario_metric.pass_threshold
    spec = PATCH_SPECS[("scenario_metric", field)]
    iteration = RsiIteration(
        loop_id=loop.id,
        iteration_index=int(loop.current_iteration or 0) + 1,
        status="reviewing",
        baseline_eval_id=env.baseline.id,
        metrics={
            "decision_metrics": {"decision": decision, "reason": "test decision"},
            "baseline": {},
            "candidate": {},
            "delta": {},
            "train": {},
            "holdout": {},
        },
        proposal_count=1,
    )
    db.add(iteration)
    db.flush()
    proposal = RsiProposal(
        loop_id=loop.id,
        iteration_id=iteration.id,
        target_type="scenario_metric",
        target_id=env.scenario_metric.id,
        field=field,
        operation="set",
        before_value=before_value,
        after_value=after_value,
        rationale="测试提案",
        evidence={"failed_row_ids": [env.rows[0].id], "reason": "低分"},
        risk_level=spec.risk,
        requires_review=True,
        status="validated",
    )
    db.add(proposal)
    loop.current_iteration = iteration.iteration_index
    loop.status = "awaiting_review"
    db.commit()
    db.refresh(iteration)
    db.refresh(proposal)
    return iteration, proposal
