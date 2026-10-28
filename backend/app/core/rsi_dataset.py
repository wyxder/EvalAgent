"""P1: derive an append-only hard-case dataset from RSI failures.

The original dataset is never modified. Rows that fall into the loop's holdout
slice are skipped so the acceptance set stays clean.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

from app.core.rsi_policy import load_eval_rows, reference_row_pass, resolve_holdout


def _frozen_thresholds(loop, db) -> dict[str, float]:
    if loop.reference_thresholds:
        return {str(k): float(v) for k, v in loop.reference_thresholds.items()}
    from app.core.rsi_policy import frozen_reference_thresholds
    from app.models.evaluation import EvalTask

    task = db.query(EvalTask).filter(EvalTask.id == loop.baseline_eval_id).first()
    return frozen_reference_thresholds((task.scenario_snapshot or {}) if task else {})


def _failed_row_ids(db, loop, thresholds: dict[str, float], limit: int = 50) -> list[int]:
    from app.models.rsi import RsiIteration

    iteration = (
        db.query(RsiIteration)
        .filter(RsiIteration.loop_id == loop.id, RsiIteration.candidate_eval_id.isnot(None))
        .order_by(RsiIteration.iteration_index.desc())
        .first()
    )
    task_id = iteration.candidate_eval_id if iteration is not None else loop.baseline_eval_id
    rows = load_eval_rows(db, task_id)
    return [
        row.row_id
        for row in rows
        if not reference_row_pass(row, thresholds)
    ][:limit]


def create_hard_case_dataset(
    db,
    loop,
    *,
    row_ids: Iterable[int] | None = None,
    iteration_id: int | None = None,
    name: str | None = None,
) -> dict[str, Any]:
    from app.models.dataset import Dataset, DatasetRow
    from app.models.rsi import RsiIteration

    source = db.query(Dataset).filter(Dataset.id == loop.dataset_id).first()
    if source is None:
        raise ValueError("源数据集不存在")

    thresholds = _frozen_thresholds(loop, db)
    requested = [int(item) for item in (row_ids or [])]
    if not requested:
        if iteration_id is not None:
            iteration = db.query(RsiIteration).filter(RsiIteration.id == iteration_id).first()
            if iteration is not None and iteration.candidate_eval_id:
                rows = load_eval_rows(db, iteration.candidate_eval_id)
                requested = [
                    row.row_id for row in rows if not reference_row_pass(row, thresholds)
                ][:50]
        if not requested:
            requested = _failed_row_ids(db, loop, thresholds)

    all_ids = [
        int(row[0])
        for row in db.query(DatasetRow.id).filter(DatasetRow.dataset_id == source.id).all()
    ]
    holdout = resolve_holdout(loop, all_ids)
    holdout_ids = set(holdout["holdout_row_ids"]) if holdout["enabled"] else set()

    selected = []
    skipped: list[int] = []
    seen: set[int] = set()
    for row_id in requested:
        if row_id in seen:
            continue
        seen.add(row_id)
        if row_id in holdout_ids:
            skipped.append(row_id)
            continue
        selected.append(row_id)
    if not selected:
        raise ValueError("没有可写入派生数据集的 train 失败行")

    rows = (
        db.query(DatasetRow)
        .filter(DatasetRow.dataset_id == source.id, DatasetRow.id.in_(selected))
        .order_by(DatasetRow.row_index)
        .all()
    )
    if not rows:
        raise ValueError("指定的行不存在于源数据集")

    dataset_name = name or (
        f"[RSI hard-case] {loop.name} · {datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    )
    dataset = Dataset(
        name=dataset_name[:200],
        description=(
            f"由 RSI 自进化循环 #{loop.id} 的失败样本派生；源数据集 #{source.id}。"
            "只追加、不修改、不删除；holdout 行已排除。"
        ),
        sample_type=source.sample_type,
        field_schema=source.field_schema,
        row_count=0,
    )
    db.add(dataset)
    db.flush()

    created = 0
    for index, row in enumerate(rows):
        data = dict(row.data or {})
        data["_rsi_origin"] = {
            "loop_id": loop.id,
            "iteration_id": iteration_id,
            "source_dataset_id": source.id,
            "source_row_id": row.id,
        }
        db.add(
            DatasetRow(
                dataset_id=dataset.id,
                row_index=index,
                data=data,
            )
        )
        created += 1
    dataset.row_count = created
    db.commit()
    db.refresh(dataset)
    return {
        "dataset_id": dataset.id,
        "dataset_name": dataset.name,
        "created_rows": created,
        "skipped_row_ids": skipped,
    }
