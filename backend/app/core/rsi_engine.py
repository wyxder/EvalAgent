"""RSI loop orchestration: state machine, threads, logging and recovery.

The engine runs iterations sequentially in a background thread (matching the
existing evaluation/blind-test/RAG job pattern). It never modifies the
evaluation engine's scoring logic: candidates run through a frozen
``scenario_snapshot`` on a throw-away ``EvalTask``.
"""

from __future__ import annotations

import asyncio
import threading
import time
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings
from app.core.rsi_diagnosis import diagnose_failures
from app.core.rsi_patch import (
    apply_patch,
    build_candidate_snapshot_for_loop,
    candidate_endpoint_config,
    rollback_iteration,
    rollback_version,
    validate_patch,
)
from app.core.rsi_policy import (
    build_iteration_metrics,
    budget_stop_reason,
    count_llm_metric_calls,
    elapsed_minutes,
    estimate_llm_calls,
    frozen_reference_thresholds,
    load_eval_rows,
    merge_acceptance_policy,
    resolve_budget,
    resolve_holdout,
    summarize_rows,
)
from app.core.rsi_proposer import create_proposal_rows, generate_proposals
from app.core.rsi_regression import (
    create_shadow_task,
    dataset_row_ids,
    llm_metric_count,
    run_shadow_evaluation,
)
from app.models.evaluation import EvalTask
from app.models.llm_config import LLMConfig
from app.models.rsi import RsiConfigVersion, RsiIteration, RsiLoop, RsiProposal


class RsiStateError(Exception):
    """The loop/iteration is not in a state that allows the operation (422)."""


class RsiConflictError(Exception):
    """A conflicting loop already exists or the loop was already started (409)."""


ACTIVE_ITERATION_STATUSES = {"pending", "diagnosing", "proposing", "validating", "evaluating"}
TERMINAL_LOOP_STATUSES = {"completed", "failed", "cancelled"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _log(loop: RsiLoop, message: str) -> None:
    timestamp = _now().strftime("%H:%M:%S")
    loop.logs = (loop.logs or "") + f"[{timestamp}] {message}\n"


def _reload(db, loop_id: int) -> RsiLoop | None:
    db.expire_all()
    return db.query(RsiLoop).filter(RsiLoop.id == loop_id).first()


def _usage(loop: RsiLoop) -> dict[str, Any]:
    return {
        "llm_calls": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "elapsed_ms": 0,
        "evaluations": 0,
        "consecutive_no_gain": 0,
        **(loop.usage or {}),
    }


def _add_usage(
    loop: RsiLoop,
    *,
    llm_calls: int = 0,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    elapsed_ms: int = 0,
    evaluations: int = 0,
) -> None:
    usage = _usage(loop)
    usage["llm_calls"] = int(usage.get("llm_calls") or 0) + int(llm_calls)
    usage["prompt_tokens"] = int(usage.get("prompt_tokens") or 0) + int(prompt_tokens)
    usage["completion_tokens"] = int(usage.get("completion_tokens") or 0) + int(completion_tokens)
    usage["elapsed_ms"] = int(usage.get("elapsed_ms") or 0) + int(elapsed_ms)
    usage["evaluations"] = int(usage.get("evaluations") or 0) + int(evaluations)
    loop.usage = usage


def _bump_no_gain(loop: RsiLoop) -> int:
    usage = _usage(loop)
    usage["consecutive_no_gain"] = int(usage.get("consecutive_no_gain") or 0) + 1
    loop.usage = usage
    return usage["consecutive_no_gain"]


def _reset_no_gain(loop: RsiLoop) -> None:
    usage = _usage(loop)
    usage["consecutive_no_gain"] = 0
    loop.usage = usage


def _cost_since(loop: RsiLoop, before: dict[str, Any], started: float) -> dict[str, Any]:
    after = _usage(loop)

    def delta(key: str) -> int:
        return int(after.get(key) or 0) - int(before.get(key) or 0)

    return {
        "llm_calls": delta("llm_calls"),
        "prompt_tokens": delta("prompt_tokens"),
        "completion_tokens": delta("completion_tokens"),
        "elapsed_ms": int((time.time() - started) * 1000),
    }


def launch_rsi_loop(loop_id: int, session_factory=None) -> None:
    """Start the loop in a daemon thread, matching existing long-task modules."""

    if session_factory is None:
        from app.core.database import SessionLocal

        session_factory = SessionLocal

    def runner() -> None:
        asyncio.run(run_rsi_loop(loop_id, session_factory))

    threading.Thread(target=runner, name=f"rsi-loop-{loop_id}", daemon=True).start()


# Backwards-compatible private alias used in the design document.
_launch_rsi_loop = launch_rsi_loop


def _cancel_candidate_tasks(db, loop_id: int, reason: str) -> None:
    tasks = (
        db.query(EvalTask)
        .filter(
            EvalTask.rsi_loop_id == loop_id,
            EvalTask.status.in_(["pending", "running"]),
        )
        .all()
    )
    for task in tasks:
        task.status = "cancelled"
        task.error_message = reason[:2000]
        task.finished_at = _now()
        task.logs = (task.logs or "") + f"[RSI] {reason}\n"


def _complete_loop(db, loop: RsiLoop, reason: str) -> None:
    loop.status = "completed"
    loop.finished_at = _now()
    _log(loop, f"循环结束：{reason}")
    db.commit()


def _fail_loop(db, loop: RsiLoop, reason: str) -> None:
    loop.status = "failed"
    loop.error_message = reason[:2000]
    loop.finished_at = _now()
    _log(loop, f"循环失败：{reason}")
    _cancel_candidate_tasks(db, loop.id, f"RSI loop failed: {reason}")
    db.commit()


def _objective_reached(loop: RsiLoop, metrics: dict[str, Any]) -> bool:
    if loop.objective_target is None:
        return False
    objective = (metrics.get("decision_metrics") or {}).get("objective") or {}
    candidate = objective.get("candidate")
    try:
        return candidate is not None and float(candidate) >= float(loop.objective_target)
    except (TypeError, ValueError):
        return False


def _accept_iteration(
    db,
    loop: RsiLoop,
    iteration: RsiIteration,
    *,
    actor: str,
    source: str,
) -> None:
    proposals = (
        db.query(RsiProposal)
        .filter(
            RsiProposal.iteration_id == iteration.id,
            RsiProposal.status == "validated",
        )
        .order_by(RsiProposal.id)
        .all()
    )
    if not proposals:
        raise RsiStateError("没有可采纳的提案")
    baseline_task = db.query(EvalTask).filter(EvalTask.id == loop.baseline_eval_id).first()
    snapshot = (baseline_task.scenario_snapshot or {}) if baseline_task is not None else {}
    if not snapshot:
        raise RsiStateError("基线评估缺少 scenario_snapshot，无法写回")
    drifted: list[str] = []
    for proposal in proposals:
        errors = validate_patch(db, loop, proposal, snapshot)
        if errors:
            drifted.append(f"提案 #{proposal.id}: {'；'.join(errors)}")
    if drifted:
        raise RsiStateError("写回前漂移复校验失败：" + " | ".join(drifted)[:1500])
    try:
        for proposal in proposals:
            apply_patch(db, proposal, actor=actor, source=source)
        iteration.status = "accepted"
        iteration.decision = "accepted"
        iteration.decision_reason = (
            f"{iteration.decision_reason or '采纳候选配置'}；"
            f"已写回 {len(proposals)} 条配置并生成版本快照"
        )
        iteration.finished_at = _now()
        loop.best_iteration_id = iteration.id
        if iteration.candidate_eval_id is not None:
            loop.baseline_eval_id = iteration.candidate_eval_id
            loop.final_eval_id = iteration.candidate_eval_id
        _reset_no_gain(loop)
        _log(loop, f"采纳第 {iteration.iteration_index} 轮候选配置（{len(proposals)} 条提案）")
        db.commit()
    except Exception:
        db.rollback()
        raise


async def _run_iteration(
    db,
    loop: RsiLoop,
    iteration: RsiIteration,
    session_factory,
) -> str:
    usage_before = _usage(loop)
    started = time.time()

    def finish(status: str, decision: str | None, reason: str, error: str | None = None) -> None:
        iteration.status = status
        if decision is not None:
            iteration.decision = decision
        iteration.decision_reason = reason
        iteration.error_message = error
        iteration.finished_at = _now()
        iteration.cost = _cost_since(loop, usage_before, started)
        db.commit()

    try:
        iteration.status = "diagnosing"
        db.commit()

        baseline_task = db.query(EvalTask).filter(EvalTask.id == loop.baseline_eval_id).first()
        if baseline_task is None:
            raise RuntimeError("基线评估任务不存在")
        snapshot = baseline_task.scenario_snapshot or {}
        if not snapshot:
            raise RuntimeError("基线评估缺少 scenario_snapshot，请重新创建基线评测")

        thresholds = frozen_reference_thresholds(snapshot)
        row_ids = dataset_row_ids(db, loop.dataset_id)
        holdout = resolve_holdout(loop, row_ids)
        baseline_rows = load_eval_rows(db, baseline_task.id)
        baseline_summary = summarize_rows(baseline_rows, thresholds)
        baseline_summary["reference_thresholds"] = thresholds

        proposer_config = (
            db.query(LLMConfig)
            .filter(LLMConfig.id == (loop.proposer_llm_config_id or loop.llm_config_id))
            .first()
        )

        _log(
            loop,
            f"第 {iteration.iteration_index} 轮：train {len(holdout['train_row_ids'])} 行，"
            f"holdout {len(holdout['holdout_row_ids'])} 行"
            + (f"（{holdout['disabled_reason']}）" if not holdout["enabled"] else ""),
        )
        db.commit()

        diagnosis = await diagnose_failures(
            db,
            loop,
            baseline_rows,
            baseline_summary,
            snapshot,
            train_row_ids=set(holdout["train_row_ids"]),
            reference_thresholds=thresholds,
            llm_config=proposer_config,
        )
        diagnosis_usage = diagnosis.get("llm_usage") or {}
        _add_usage(
            loop,
            llm_calls=int(diagnosis_usage.get("llm_calls") or 0),
            prompt_tokens=int(diagnosis_usage.get("prompt_tokens") or 0),
            completion_tokens=int(diagnosis_usage.get("completion_tokens") or 0),
        )
        iteration.diagnosis = diagnosis
        iteration.status = "proposing"
        _log(loop, f"归因完成：{diagnosis.get('summary', '')[:200]}")
        db.commit()

        proposal_result = await generate_proposals(
            loop,
            diagnosis,
            snapshot,
            train_row_ids=holdout["train_row_ids"],
            llm_config=proposer_config,
        )
        proposal_usage = proposal_result.get("usage") or {}
        _add_usage(
            loop,
            llm_calls=int(proposal_usage.get("llm_calls") or 0),
            prompt_tokens=int(proposal_usage.get("prompt_tokens") or 0),
            completion_tokens=int(proposal_usage.get("completion_tokens") or 0),
        )
        if proposal_result.get("error"):
            _bump_no_gain(loop)
            finish("rejected", "rejected", f"提案生成失败：{proposal_result['error']}")
            return "continue"

        proposal_rows = create_proposal_rows(db, loop, iteration, proposal_result["proposals"])
        iteration.status = "validating"
        db.commit()
        validation_details: list[dict[str, Any]] = []
        valid: list[RsiProposal] = []
        for proposal in proposal_rows:
            errors = validate_patch(db, loop, proposal, snapshot)
            if errors:
                proposal.status = "rejected"
                evidence = dict(proposal.evidence or {})
                evidence["validation_errors"] = errors
                proposal.evidence = evidence
                validation_details.append({"proposal_id": proposal.id, "errors": errors})
            else:
                proposal.status = "validated"
                valid.append(proposal)
        iteration.proposal_count = len(proposal_rows)
        validation = {
            "total": len(proposal_rows),
            "valid": len(valid),
            "rejected": len(proposal_rows) - len(valid),
            "rejected_details": validation_details,
            "risks": {str(item.id): item.risk_level for item in proposal_rows},
        }
        db.commit()

        if not valid:
            _bump_no_gain(loop)
            finish(
                "rejected",
                "rejected",
                f"本轮 {len(proposal_rows)} 条提案全部未通过白名单/漂移校验",
            )
            return "continue"

        try:
            candidate_snapshot = build_candidate_snapshot_for_loop(
                loop, iteration, valid, snapshot
            )
        except ValueError as exc:
            _bump_no_gain(loop)
            finish("rejected", "rejected", f"候选快照构建失败：{exc}")
            return "continue"
        candidate_target_config = (
            candidate_endpoint_config(loop, valid)
            if loop.evaluation_mode == "endpoint"
            else None
        )

        iteration.status = "evaluating"
        db.commit()
        shadow_task = create_shadow_task(
            db, loop, iteration, candidate_snapshot, candidate_target_config
        )
        iteration.candidate_eval_id = shadow_task.id
        db.commit()
        _log(loop, f"已创建影子评估任务 #{shadow_task.id}，开始候选回归")
        db.commit()

        await run_shadow_evaluation(shadow_task.id, session_factory)
        db.expire_all()
        shadow_task = db.query(EvalTask).filter(EvalTask.id == shadow_task.id).first()
        if shadow_task is None or shadow_task.status != "completed":
            status = shadow_task.status if shadow_task else "missing"
            detail = (shadow_task.error_message if shadow_task else "") or ""
            _bump_no_gain(loop)
            finish(
                "rejected",
                "rejected",
                f"候选评估未完成（{status}）：{detail[:500]}",
            )
            return "continue"

        candidate_rows = load_eval_rows(db, shadow_task.id)
        policy = loop.acceptance_policy or merge_acceptance_policy(
            None, auto_apply_low_risk=loop.auto_apply_low_risk
        )
        metrics = build_iteration_metrics(
            baseline_rows=baseline_rows,
            candidate_rows=candidate_rows,
            train_row_ids=holdout["train_row_ids"],
            holdout_row_ids=holdout["holdout_row_ids"],
            holdout_enabled=holdout["enabled"],
            policy=policy,
            objective_mode=loop.objective_mode or "reference_pass_rate",
            objective_metric=loop.objective_metric,
            reference_thresholds=thresholds,
            objective_target=loop.objective_target,
            validation=validation,
        )
        iteration.metrics = metrics
        iteration.baseline_eval_id = baseline_task.id
        _add_usage(
            loop,
            evaluations=1,
            llm_calls=count_llm_metric_calls(candidate_rows),
        )
        db.commit()

        judge = metrics.get("decision_metrics") or {}
        recommended = judge.get("decision") or "inconclusive"
        requires_review = any(item.requires_review for item in valid)
        auto_apply = (
            bool(loop.auto_apply_low_risk)
            and bool(judge.get("auto_accept_eligible"))
            and not requires_review
            and all(item.risk_level == "low" for item in valid)
        )

        if recommended == "rejected":
            _bump_no_gain(loop)
            finish("rejected", "rejected", judge.get("reason") or "候选配置未通过验收")
            return "continue"

        if auto_apply and recommended == "accepted":
            iteration.decision_reason = judge.get("reason")
            _accept_iteration(db, loop, iteration, actor="system", source="auto")
            if _objective_reached(loop, metrics):
                return "complete"
            return "continue"

        iteration.status = "reviewing"
        iteration.decision = None
        iteration.decision_reason = (
            f"等待人工审批（系统建议：{recommended}；"
            f"{judge.get('reason') or '无判定理由'}）"
        )
        iteration.finished_at = None
        iteration.cost = _cost_since(loop, usage_before, started)
        db.commit()
        _log(loop, f"第 {iteration.iteration_index} 轮进入人工审批：{recommended}")
        db.commit()
        return "awaiting_review"

    except Exception as exc:
        db.rollback()
        try:
            failed_iteration = db.query(RsiIteration).filter(RsiIteration.id == iteration.id).first()
            failed_loop = db.query(RsiLoop).filter(RsiLoop.id == loop.id).first()
            if failed_iteration is not None:
                failed_iteration.status = "failed"
                failed_iteration.error_message = str(exc)[:2000]
                failed_iteration.finished_at = _now()
                if failed_loop is not None:
                    failed_iteration.cost = _cost_since(failed_loop, usage_before, started)
            if failed_loop is not None:
                iteration_index = failed_iteration.iteration_index if failed_iteration else "?"
                _log(failed_loop, f"第 {iteration_index} 轮异常：{str(exc)[:300]}")
            db.commit()
        except Exception:
            db.rollback()
        return "failed"


async def run_rsi_loop(loop_id: int, session_factory) -> None:
    """Sequentially execute iterations until review/budget/convergence/cancel."""

    db = session_factory()
    try:
        loop = _reload(db, loop_id)
        if loop is None:
            return
        if loop.status in TERMINAL_LOOP_STATUSES or loop.status == "awaiting_review":
            return
        if loop.status == "draft":
            loop.status = "running"
            loop.started_at = loop.started_at or _now()
            _log(loop, "RSI 循环启动")
            db.commit()

        while True:
            loop = _reload(db, loop_id)
            if loop is None:
                return
            if loop.status == "cancelled":
                _log(loop, "循环已被用户取消")
                db.commit()
                return
            if loop.status in {"completed", "failed", "awaiting_review"}:
                return

            baseline_task = db.query(EvalTask).filter(EvalTask.id == loop.baseline_eval_id).first()
            if baseline_task is None or baseline_task.status != "completed":
                _fail_loop(db, loop, "基线评估不存在或未完成，无法继续迭代")
                return
            snapshot = baseline_task.scenario_snapshot or {}
            if not snapshot:
                _fail_loop(db, loop, "基线评估缺少 scenario_snapshot，请重新创建基线评测")
                return

            row_ids = dataset_row_ids(db, loop.dataset_id)
            if not row_ids:
                _fail_loop(db, loop, "数据集没有可评估的行")
                return
            llm_count = llm_metric_count(snapshot)
            estimate = estimate_llm_calls(len(row_ids), llm_count, resolve_budget(loop))
            stop_reason = budget_stop_reason(
                loop, next_estimate=estimate, llm_metric_count=llm_count
            )
            if stop_reason:
                _complete_loop(db, loop, stop_reason)
                return

            iteration = RsiIteration(
                loop_id=loop.id,
                iteration_index=int(loop.current_iteration or 0) + 1,
                status="pending",
                baseline_eval_id=loop.baseline_eval_id,
                started_at=_now(),
            )
            db.add(iteration)
            loop.current_iteration = iteration.iteration_index
            _log(loop, f"开始第 {iteration.iteration_index} 轮迭代")
            db.commit()
            db.refresh(iteration)

            outcome = await _run_iteration(db, loop, iteration, session_factory)
            loop = _reload(db, loop_id)
            if loop is None:
                return
            if outcome == "awaiting_review":
                loop.status = "awaiting_review"
                db.commit()
                return
            if outcome == "failed":
                _fail_loop(db, loop, iteration.error_message or "迭代执行异常")
                return
            if outcome == "complete":
                _complete_loop(db, loop, "达到目标值或已收敛")
                return
            # "continue"
            if loop.status == "cancelled":
                _log(loop, "循环已被用户取消")
                db.commit()
                return
    except Exception as exc:
        try:
            db.rollback()
            loop = _reload(db, loop_id)
            if loop is not None and loop.status == "running":
                _fail_loop(db, loop, f"RSI 引擎异常：{str(exc)[:1000]}")
        except Exception:
            db.rollback()
    finally:
        db.close()


def approve_iteration(
    db,
    iteration_id: int,
    *,
    actor: str | None = None,
    resume: bool = True,
) -> RsiIteration:
    iteration = db.query(RsiIteration).filter(RsiIteration.id == iteration_id).first()
    if iteration is None:
        raise LookupError("迭代不存在")
    loop = db.query(RsiLoop).filter(RsiLoop.id == iteration.loop_id).first()
    if loop is None:
        raise LookupError("循环不存在")
    if loop.status != "awaiting_review" or iteration.status != "reviewing":
        raise RsiStateError("当前迭代不在等待审批状态")
    judge = (iteration.metrics or {}).get("decision_metrics") or {}
    if judge.get("decision") == "rejected":
        raise RsiStateError("系统判定为 rejected，不能直接采纳")

    _accept_iteration(
        db,
        loop,
        iteration,
        actor=actor or "human",
        source="manual",
    )
    if resume:
        loop.status = "running"
        loop.finished_at = None
        db.commit()
    else:
        loop.status = "completed"
        loop.finished_at = _now()
        _log(loop, "人工审批完成，按请求停止循环")
        db.commit()
    db.refresh(iteration)
    return iteration


def reject_iteration(
    db,
    iteration_id: int,
    *,
    reason: str,
    actor: str | None = None,
    resume: bool = False,
) -> RsiIteration:
    iteration = db.query(RsiIteration).filter(RsiIteration.id == iteration_id).first()
    if iteration is None:
        raise LookupError("迭代不存在")
    loop = db.query(RsiLoop).filter(RsiLoop.id == iteration.loop_id).first()
    if loop is None:
        raise LookupError("循环不存在")
    if loop.status != "awaiting_review" or iteration.status != "reviewing":
        raise RsiStateError("当前迭代不在等待审批状态")

    proposals = (
        db.query(RsiProposal)
        .filter(
            RsiProposal.iteration_id == iteration.id,
            RsiProposal.status == "validated",
        )
        .all()
    )
    for proposal in proposals:
        proposal.status = "rejected"
        proposal.decided_by = actor or "human"
        proposal.decided_at = _now()
        proposal.decision_source = "manual"

    iteration.status = "rejected"
    iteration.decision = "rejected"
    iteration.decision_reason = reason[:2000]
    iteration.finished_at = _now()
    _bump_no_gain(loop)
    _log(loop, f"第 {iteration.iteration_index} 轮被人工驳回：{reason[:200]}")
    if resume:
        loop.status = "running"
        loop.finished_at = None
    else:
        loop.status = "completed"
        loop.finished_at = _now()
    db.commit()
    db.refresh(iteration)
    return iteration


def cancel_loop(db, loop: RsiLoop, *, actor: str | None = None) -> RsiLoop:
    if loop.status in TERMINAL_LOOP_STATUSES:
        raise RsiStateError("循环已经结束")
    loop.status = "cancelled"
    loop.finished_at = _now()
    active = (
        db.query(RsiIteration)
        .filter(
            RsiIteration.loop_id == loop.id,
            RsiIteration.status.in_(list(ACTIVE_ITERATION_STATUSES) + ["reviewing"]),
        )
        .all()
    )
    for iteration in active:
        iteration.status = "failed"
        iteration.error_message = "循环已取消"
        iteration.finished_at = _now()
    _log(loop, f"循环被取消（操作人：{actor or 'human'}）")
    _cancel_candidate_tasks(db, loop.id, "RSI loop cancelled by user")
    db.commit()
    db.refresh(loop)
    return loop


def rollback_loop(
    db,
    loop: RsiLoop,
    *,
    version_id: int | None = None,
    iteration_id: int | None = None,
    actor: str | None = None,
) -> list[int]:
    if loop.status == "running":
        raise RsiStateError("循环正在运行，请先取消后再回滚")
    rolled: list[int] = []
    if version_id is not None:
        version = (
            db.query(RsiConfigVersion)
            .filter(RsiConfigVersion.id == version_id)
            .first()
        )
        if version is None:
            raise LookupError("版本不存在")
        if version.loop_id is not None and int(version.loop_id) != int(loop.id):
            raise LookupError("版本不属于该循环")
        rolled.append(rollback_version(db, version.id, actor=actor or "human"))
        target_iteration_id = version.iteration_id
    elif iteration_id is not None:
        iteration = (
            db.query(RsiIteration)
            .filter(RsiIteration.id == iteration_id)
            .first()
        )
        if iteration is None or int(iteration.loop_id) != int(loop.id):
            raise LookupError("迭代不存在")
        rolled = rollback_iteration(db, iteration.id, actor=actor or "human")
        target_iteration_id = iteration.id
    else:
        raise ValueError("version_id 与 iteration_id 至少提供一个")

    if target_iteration_id is not None:
        iteration = (
            db.query(RsiIteration)
            .filter(RsiIteration.id == target_iteration_id)
            .first()
        )
        if iteration is not None:
            iteration.status = "rolled_back"
            iteration.decision = "rolled_back"
            iteration.decision_reason = "配置已回滚"
            if loop.best_iteration_id == iteration.id:
                loop.best_iteration_id = None
            if iteration.baseline_eval_id:
                loop.baseline_eval_id = iteration.baseline_eval_id
    _log(loop, f"已回滚 {len(rolled)} 个版本（操作人：{actor or 'human'}）")
    db.commit()
    return rolled


def recover_stale_rsi_loop(db, loop_id: int | None = None) -> int:
    """Fail loops that exceeded their wall-clock budget (e.g. after a restart)."""

    query = db.query(RsiLoop).filter(RsiLoop.status == "running")
    if loop_id is not None:
        query = query.filter(RsiLoop.id == loop_id)
    recovered = 0
    for loop in query.all():
        budget = resolve_budget(loop)
        max_minutes = float(budget.get("max_minutes") or settings.RSI_MAX_MINUTES)
        if elapsed_minutes(loop.started_at) <= max_minutes + 1:
            continue
        loop.status = "failed"
        loop.error_message = f"运行超过预算时长 {max_minutes} 分钟，已自动终止"
        loop.finished_at = _now()
        _log(loop, loop.error_message)
        _cancel_candidate_tasks(db, loop.id, loop.error_message)
        recovered += 1
    if recovered:
        db.commit()
    return recovered
