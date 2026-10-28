"""Pure-policy tests: stable holdout, threshold-independent acceptance, budget."""

from types import SimpleNamespace

from app.core.rsi_policy import (
    RowScore,
    budget_stop_reason,
    build_iteration_metrics,
    frozen_reference_thresholds,
    judge_iteration,
    merge_acceptance_policy,
    merge_budget,
    split_row_ids,
    summarize_rows,
)


def _row(row_id: int, score: float, *, error: str | None = None, **extra) -> RowScore:
    scores = {"faithfulness": score, **extra}
    return RowScore(
        row_id=row_id,
        row_index=row_id,
        is_pass=score >= 0.7,
        error=error,
        scores=scores,
        reasons={"faithfulness": "reason"},
    )


def test_split_row_ids_is_stable_and_respects_ratio():
    ids = list(range(1, 101))
    train_a, holdout_a = split_row_ids(7, ids, 0.3)
    train_b, holdout_b = split_row_ids(7, ids, 0.3)

    assert (train_a, holdout_a) == (train_b, holdout_b)
    assert set(train_a).isdisjoint(holdout_a)
    assert sorted(train_a + holdout_a) == ids
    assert 20 <= len(holdout_a) <= 40


def test_summarize_rows_uses_reference_thresholds_not_native_pass():
    rows = [
        RowScore(
            row_id=1,
            row_index=1,
            is_pass=True,
            scores={"faithfulness": 0.5},
        ),
        _row(2, 0.9),
        _row(3, 0.6, error="judge timeout"),
    ]
    summary = summarize_rows(rows, {"faithfulness": 0.7})

    # Row 1 claims a native pass through is_pass=True above, but the frozen
    # reference threshold is what decides pass/fail here.
    assert summary["total"] == 3
    assert summary["pass_count"] == 1
    assert summary["fail_count"] == 2
    assert summary["error_count"] == 1
    assert summary["pass_rate"] == round(1 / 3, 6)


def test_judge_accepts_holdout_gain_and_marks_auto_eligible():
    baseline = [_row(index, 0.4) for index in range(1, 11)]
    candidate = [_row(index, 0.9) for index in range(1, 11)]
    policy = merge_acceptance_policy(
        {"sampling": {"min_rows_for_auto_accept": 4}, "objective": {"min_gain": 0.03}}
    )

    judge = judge_iteration(
        baseline_rows=baseline,
        candidate_rows=candidate,
        train_row_ids=range(1, 7),
        holdout_row_ids=range(7, 11),
        holdout_enabled=True,
        policy=policy,
        objective_mode="reference_pass_rate",
        objective_metric=None,
        reference_thresholds={"faithfulness": 0.7},
    )

    assert judge["decision"] == "accepted"
    assert judge["objective"]["gain"] == 1.0
    assert judge["holdout"]["rows"] == 4
    assert judge["auto_accept_eligible"] is True
    assert judge["migration"]["fixed"] == 4


def test_judge_requires_holdout_for_auto_acceptance():
    baseline = [_row(index, 0.4) for index in range(1, 7)]
    candidate = [_row(index, 0.9) for index in range(1, 7)]
    policy = merge_acceptance_policy({"sampling": {"min_rows_for_auto_accept": 5}})

    judge = judge_iteration(
        baseline_rows=baseline,
        candidate_rows=candidate,
        train_row_ids=range(1, 7),
        holdout_row_ids=[],
        holdout_enabled=False,
        policy=policy,
        objective_mode="reference_pass_rate",
        objective_metric=None,
        reference_thresholds={"faithfulness": 0.7},
    )

    assert judge["decision"] == "inconclusive"
    assert judge["auto_accept_eligible"] is False
    assert "holdout" in judge["reason"]


def test_judge_rejects_protected_metric_drop():
    baseline = [_row(index, 0.5, answer_quality=0.5) for index in range(1, 11)]
    candidate = [_row(index, 0.9, answer_quality=0.2) for index in range(1, 11)]
    policy = merge_acceptance_policy({"constraints": {"max_metric_drop": 0.02}})

    judge = judge_iteration(
        baseline_rows=baseline,
        candidate_rows=candidate,
        train_row_ids=range(1, 7),
        holdout_row_ids=range(7, 11),
        holdout_enabled=True,
        policy=policy,
        objective_mode="reference_pass_rate",
        objective_metric=None,
        reference_thresholds={"faithfulness": 0.7, "answer_quality": 0.7},
    )

    assert judge["decision"] == "rejected"
    assert any("answer_quality" in item for item in judge["violations"])


def test_build_iteration_metrics_keeps_slices_and_thresholds():
    baseline = [_row(index, 0.4) for index in range(1, 11)]
    candidate = [_row(index, 0.9) for index in range(1, 11)]
    metrics = build_iteration_metrics(
        baseline_rows=baseline,
        candidate_rows=candidate,
        train_row_ids=range(1, 7),
        holdout_row_ids=range(7, 11),
        holdout_enabled=True,
        policy=merge_acceptance_policy({"sampling": {"min_rows_for_auto_accept": 4}}),
        objective_mode="reference_pass_rate",
        objective_metric=None,
        reference_thresholds={"faithfulness": 0.7},
        objective_target=None,
        validation={"valid": 1},
    )

    assert metrics["reference_thresholds"] == {"faithfulness": 0.7}
    assert metrics["train"]["baseline"]["total"] == 6
    assert metrics["holdout"]["candidate"]["pass_count"] == 4
    assert metrics["validation"] == {"valid": 1}
    assert metrics["decision_metrics"]["decision"] == "accepted"


def test_budget_stop_reason_respects_iterations_and_calls():
    loop = SimpleNamespace(
        current_iteration=2,
        usage={"llm_calls": 5, "elapsed_ms": 0, "consecutive_no_gain": 0},
        budget={"max_iterations": 2},
        started_at=None,
    )
    reason = budget_stop_reason(loop, next_estimate=10, llm_metric_count=1)
    assert reason and "最大迭代轮次" in reason

    loop.current_iteration = 0
    loop.budget = {"max_iterations": 5, "max_llm_calls": 10}
    reason = budget_stop_reason(loop, next_estimate=10, llm_metric_count=1)
    assert reason and "LLM 调用预算不足" in reason


def test_merge_defaults_and_frozen_thresholds():
    budget = merge_budget({"max_iterations": 2})
    assert budget["max_iterations"] == 2
    assert budget["max_rows_per_iteration"] >= 1

    policy = merge_acceptance_policy(None, auto_apply_low_risk=True)
    assert policy["review"]["auto_apply_low_risk"] is True
    assert policy["objective"]["mode"] == "reference_pass_rate"

    snapshot = {
        "metrics": [
            {"pass_threshold": 0.6, "metric_definition": {"name": "a"}},
            {"pass_threshold": None, "metric_definition": {"name": "b"}},
        ]
    }
    assert frozen_reference_thresholds(snapshot) == {"a": 0.6, "b": 0.7}
