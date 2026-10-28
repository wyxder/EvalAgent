"""Shadow regression for RSI candidates.

A candidate never mutates the live scenario: it is materialised as a frozen
``scenario_snapshot`` on a throw-away ``EvalTask`` and executed by the existing
``run_evaluation`` entry point. The engine therefore stays untouched.
"""

from __future__ import annotations

from typing import Any, Iterable

from app.core.evaluation_engine import run_evaluation
from app.core.rsi_policy import RowScore, load_eval_rows


LLM_METRIC_TYPES = {
    "numeric",
    "discrete",
    "aspect_critic",
}
NON_LLM_METRIC_TYPES = {
    "code_retrieval_hit_rate",
    "code_retrieval_mrr",
    "builtin_tool_call_accuracy",
    "builtin_argument_correctness",
    "builtin_step_efficiency",
}


def dataset_row_ids(db, dataset_id: int) -> list[int]:
    from app.models.dataset import DatasetRow

    rows = (
        db.query(DatasetRow.id)
        .filter(DatasetRow.dataset_id == dataset_id)
        .order_by(DatasetRow.row_index)
        .all()
    )
    return [int(row[0]) for row in rows]


def llm_metric_count(snapshot: dict[str, Any]) -> int:
    count = 0
    for item in (snapshot or {}).get("metrics") or []:
        definition = item.get("metric_definition") or {}
        metric_type = str(definition.get("metric_type") or "")
        name = str(definition.get("name") or "")
        if metric_type in LLM_METRIC_TYPES:
            count += 1
        elif metric_type in NON_LLM_METRIC_TYPES:
            continue
        elif metric_type.startswith("builtin_") or name == "answer_completeness":
            count += 1
    return count


def create_shadow_task(
    db,
    loop,
    iteration,
    candidate_snapshot: dict[str, Any],
    candidate_target_config: dict[str, Any] | None = None,
):
    from app.models.evaluation import EvalTask

    task = EvalTask(
        name=f"[RSI] {loop.name} · iter {iteration.iteration_index}",
        dataset_id=loop.dataset_id,
        scenario_id=loop.scenario_id,
        llm_config_id=loop.llm_config_id,
        status="pending",
        scenario_snapshot=candidate_snapshot,
        evaluation_mode=loop.evaluation_mode or "offline",
        endpoint_target_id=loop.endpoint_target_id,
        target_config=candidate_target_config if candidate_target_config is not None else loop.target_config,
        response_mapping=loop.response_mapping,
        result_save_mode="task_only",
        rsi_loop_id=loop.id,
        rsi_iteration_id=iteration.id,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


async def run_shadow_evaluation(task_id: int, session_factory=None) -> None:
    if session_factory is None:
        from app.core.database import SessionLocal

        session_factory = SessionLocal
    await run_evaluation(task_id, session_factory)


def collect_rows(
    db,
    task_id: int,
    row_ids: Iterable[int] | None = None,
) -> list[RowScore]:
    return load_eval_rows(db, task_id, row_ids)
