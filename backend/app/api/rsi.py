"""RSI self-evolution REST API (new module, existing routers untouched)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.core.database import get_db
from app.core.evaluation_debug import run_debug_evaluation
from app.core.rsi_dataset import create_hard_case_dataset
from app.core.rsi_engine import (
    RsiStateError,
    approve_iteration,
    cancel_loop,
    launch_rsi_loop,
    reject_iteration,
    rollback_loop,
)
from app.core.rsi_patch import (
    build_candidate_snapshot_for_loop,
    candidate_endpoint_config,
    restore_version,
)
from app.core.rsi_policy import (
    frozen_reference_thresholds,
    merge_acceptance_policy,
    merge_budget,
)
from app.models.evaluation import EvalTask
from app.models.llm_config import LLMConfig
from app.models.rsi import RsiConfigVersion, RsiIteration, RsiLoop, RsiProposal
from app.schemas.evaluation import EvalDebugRequest
from app.schemas.rsi import (
    RsiApproveRequest,
    RsiCompareResponse,
    RsiConfigVersionResponse,
    RsiHardCaseRequest,
    RsiHardCaseResponse,
    RsiIterationBrief,
    RsiIterationListResponse,
    RsiIterationResponse,
    RsiLogsResponse,
    RsiLoopCreate,
    RsiLoopListResponse,
    RsiLoopResponse,
    RsiPreviewRequest,
    RsiPreviewResponse,
    RsiProposalResponse,
    RsiRejectRequest,
    RsiRollbackRequest,
    RsiRollbackResponse,
    RsiVersionListResponse,
)
from app.schemas.sensitive import redact_sensitive_mapping


def ensure_rsi_enabled() -> None:
    if not settings.RSI_ENABLED:
        raise HTTPException(
            status_code=403,
            detail="RSI 自进化功能已关闭（RSI_ENABLED=false）",
        )


router = APIRouter(
    prefix="/rsi",
    tags=["RSI"],
    dependencies=[Depends(ensure_rsi_enabled)],
)

VERSION_SCOPES = {"scenario_metric", "metric_definition", "scenario", "endpoint_target"}
ACTIVE_LOOP_STATUSES = ("running", "awaiting_review")


def _raise_http(exc: Exception) -> None:
    if isinstance(exc, LookupError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, RsiStateError):
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    raise exc


def _get_loop(db: Session, loop_id: int) -> RsiLoop:
    loop = db.query(RsiLoop).filter(RsiLoop.id == loop_id).first()
    if loop is None:
        raise HTTPException(status_code=404, detail="RSI 循环不存在")
    return loop


def _get_iteration(db: Session, iteration_id: int) -> RsiIteration:
    iteration = (
        db.query(RsiIteration)
        .options(joinedload(RsiIteration.proposals))
        .filter(RsiIteration.id == iteration_id)
        .first()
    )
    if iteration is None:
        raise HTTPException(status_code=404, detail="RSI 迭代不存在")
    return iteration


def _latest_iteration(db: Session, loop_id: int) -> RsiIteration | None:
    return (
        db.query(RsiIteration)
        .filter(RsiIteration.loop_id == loop_id)
        .order_by(RsiIteration.iteration_index.desc())
        .first()
    )


def _iteration_brief(iteration: RsiIteration) -> RsiIterationBrief:
    data = RsiIterationBrief.model_validate(iteration)
    objective = (
        ((iteration.metrics or {}).get("decision_metrics") or {}).get("objective")
        or {}
    )
    gain = objective.get("gain")
    if isinstance(gain, (int, float)):
        data.objective_gain = float(gain)
    holdout = (((iteration.metrics or {}).get("holdout") or {}).get("candidate") or {})
    holdout_rate = holdout.get("pass_rate")
    if isinstance(holdout_rate, (int, float)):
        data.holdout_pass_rate = float(holdout_rate)
    data.cost = iteration.cost
    return data


def _serialize_loop(db: Session, loop: RsiLoop) -> RsiLoopResponse:
    data = RsiLoopResponse.model_validate(loop)
    data.dataset_name = loop.dataset.name if loop.dataset is not None else None
    data.scenario_name = loop.scenario.name if loop.scenario is not None else None
    data.llm_model_name = (
        loop.llm_config.model_name if loop.llm_config is not None else None
    )
    data.proposer_model_name = (
        loop.proposer_llm_config.model_name
        if loop.proposer_llm_config is not None
        else data.llm_model_name
    )
    if loop.best_iteration_id:
        best = (
            db.query(RsiIteration)
            .filter(RsiIteration.id == loop.best_iteration_id)
            .first()
        )
        data.best_iteration = (
            _iteration_brief(best) if best is not None else None
        )
        if best is not None:
            data.best_gain = data.best_iteration.objective_gain if data.best_iteration else None
    latest = _latest_iteration(db, loop.id)
    data.latest_iteration = (
        _iteration_brief(latest) if latest is not None else None
    )
    return data


def _serialize_iteration(iteration: RsiIteration) -> RsiIterationResponse:
    data = RsiIterationResponse.model_validate(iteration)
    brief = _iteration_brief(iteration)
    data.objective_gain = brief.objective_gain
    data.holdout_pass_rate = brief.holdout_pass_rate
    data.cost = brief.cost
    data.proposals = [
        RsiProposalResponse.model_validate(item)
        for item in sorted(iteration.proposals or [], key=lambda entry: entry.id or 0)
    ]
    return data


def _serialize_version(version: RsiConfigVersion) -> RsiConfigVersionResponse:
    data = RsiConfigVersionResponse.model_validate(version)
    if data.scope == "endpoint_target":
        data.snapshot = redact_sensitive_mapping(data.snapshot)
        data.patch = redact_sensitive_mapping(data.patch)
    return data


def _snapshot_metric_names(snapshot: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    for item in snapshot.get("metrics") or []:
        name = ((item.get("metric_definition") or {}).get("name")) or ""
        if name:
            names.add(str(name))
    return names


@router.get("/loops", response_model=RsiLoopListResponse)
def list_loops(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    scenario_id: int | None = Query(None),
    keyword: str | None = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(RsiLoop).options(
        joinedload(RsiLoop.dataset),
        joinedload(RsiLoop.scenario),
        joinedload(RsiLoop.llm_config),
        joinedload(RsiLoop.proposer_llm_config),
    )
    if status:
        query = query.filter(RsiLoop.status == status)
    if scenario_id:
        query = query.filter(RsiLoop.scenario_id == scenario_id)
    if keyword:
        query = query.filter(RsiLoop.name.contains(keyword))
    total = query.count()
    loops = (
        query.order_by(RsiLoop.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return RsiLoopListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[_serialize_loop(db, loop) for loop in loops],
    )


@router.post("/loops", response_model=RsiLoopResponse, status_code=201)
def create_loop(payload: RsiLoopCreate, db: Session = Depends(get_db)):
    baseline = db.query(EvalTask).filter(EvalTask.id == payload.baseline_eval_id).first()
    if baseline is None:
        raise HTTPException(status_code=404, detail="基线评估任务不存在")
    if baseline.status != "completed":
        raise HTTPException(status_code=400, detail="基线评估尚未完成，无法创建 RSI 循环")
    if not baseline.summary_scores:
        raise HTTPException(status_code=400, detail="基线评估缺少汇总结果，无法创建 RSI 循环")

    snapshot = baseline.scenario_snapshot or {}
    if not snapshot:
        raise HTTPException(
            status_code=400,
            detail="基线评估缺少 scenario_snapshot，请重新创建基线评测后再启动自进化",
        )
    metric_names = _snapshot_metric_names(snapshot)
    objective_metric = payload.objective_metric
    if payload.objective_mode == "metric_mean" and not objective_metric:
        raise HTTPException(status_code=400, detail="metric_mean 验收模式必须指定 objective_metric")
    if objective_metric and objective_metric not in metric_names:
        raise HTTPException(
            status_code=400,
            detail=f"目标指标 {objective_metric} 不在基线快照的指标集中",
        )

    llm_config_id = payload.llm_config_id or baseline.llm_config_id
    llm_config = db.query(LLMConfig).filter(LLMConfig.id == llm_config_id).first()
    if llm_config is None:
        raise HTTPException(status_code=404, detail="评测 LLM 配置不存在")
    if payload.proposer_llm_config_id is not None:
        proposer = (
            db.query(LLMConfig)
            .filter(LLMConfig.id == payload.proposer_llm_config_id)
            .first()
        )
        if proposer is None:
            raise HTTPException(status_code=404, detail="提案 LLM 配置不存在")

    conflict = (
        db.query(RsiLoop)
        .filter(
            RsiLoop.scenario_id == baseline.scenario_id,
            RsiLoop.status.in_(ACTIVE_LOOP_STATUSES),
        )
        .first()
    )
    if conflict is not None:
        raise HTTPException(
            status_code=409,
            detail=f"场景下已存在运行中或待审批的 RSI 循环 #{conflict.id}",
        )

    policy_raw: dict[str, Any] = (
        payload.acceptance_policy.model_dump(exclude_none=True)
        if payload.acceptance_policy is not None
        else {}
    )
    if payload.holdout is not None:
        policy_raw.setdefault("sampling", {}).update(
            payload.holdout.model_dump(exclude_none=True)
        )
    objective_section = policy_raw.setdefault("objective", {})
    objective_section["metric"] = objective_metric
    objective_section["mode"] = payload.objective_mode
    policy = merge_acceptance_policy(
        policy_raw, auto_apply_low_risk=payload.auto_apply_low_risk
    )

    budget = merge_budget(
        payload.budget.model_dump(exclude_none=True) if payload.budget is not None else None
    )

    loop = RsiLoop(
        name=payload.name,
        description=payload.description,
        status="draft",
        baseline_eval_id=baseline.id,
        dataset_id=baseline.dataset_id,
        scenario_id=baseline.scenario_id,
        llm_config_id=llm_config_id,
        proposer_llm_config_id=payload.proposer_llm_config_id,
        evaluation_mode=baseline.evaluation_mode or "offline",
        endpoint_target_id=baseline.endpoint_target_id,
        target_config=baseline.target_config,
        response_mapping=baseline.response_mapping,
        result_save_mode="task_only",
        objective_metric=objective_metric,
        objective_target=payload.objective_target,
        objective_mode=payload.objective_mode,
        reference_thresholds=frozen_reference_thresholds(snapshot),
        holdout_config=dict(policy.get("sampling") or {}),
        acceptance_policy=policy,
        budget=budget,
        usage={
            "llm_calls": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "elapsed_ms": 0,
            "evaluations": 0,
            "consecutive_no_gain": 0,
        },
        current_iteration=0,
        auto_apply_low_risk=payload.auto_apply_low_risk,
        logs="",
    )
    db.add(loop)
    db.commit()
    db.refresh(loop)
    return _serialize_loop(db, loop)


@router.get("/loops/{loop_id}", response_model=RsiLoopResponse)
def get_loop(loop_id: int, db: Session = Depends(get_db)):
    loop = _get_loop(db, loop_id)
    return _serialize_loop(db, loop)


@router.post("/loops/{loop_id}/start", response_model=RsiLoopResponse)
def start_loop(loop_id: int, db: Session = Depends(get_db)):
    loop = _get_loop(db, loop_id)
    if loop.status == "running":
        raise HTTPException(status_code=409, detail="循环已在运行")
    if loop.status != "draft":
        raise HTTPException(
            status_code=409, detail=f"循环状态为 {loop.status}，不允许启动"
        )
    launch_rsi_loop(loop.id)
    db.refresh(loop)
    return _serialize_loop(db, loop)


@router.post("/loops/{loop_id}/cancel", response_model=RsiLoopResponse)
def cancel_loop_route(loop_id: int, db: Session = Depends(get_db)):
    loop = _get_loop(db, loop_id)
    try:
        cancel_loop(db, loop)
    except RsiStateError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _serialize_loop(db, loop)


@router.get("/loops/{loop_id}/logs", response_model=RsiLogsResponse)
def get_loop_logs(
    loop_id: int,
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    loop = _get_loop(db, loop_id)
    logs = loop.logs or ""
    return RsiLogsResponse(
        loop_id=loop.id,
        status=loop.status,
        current_iteration=int(loop.current_iteration or 0),
        logs=logs[offset:],
    )


@router.get("/loops/{loop_id}/iterations", response_model=RsiIterationListResponse)
def list_iterations(loop_id: int, db: Session = Depends(get_db)):
    _get_loop(db, loop_id)
    iterations = (
        db.query(RsiIteration)
        .filter(RsiIteration.loop_id == loop_id)
        .order_by(RsiIteration.iteration_index.asc())
        .all()
    )
    return RsiIterationListResponse(
        total=len(iterations),
        items=[_iteration_brief(item) for item in iterations],
    )


@router.get("/iterations/{iteration_id}", response_model=RsiIterationResponse)
def get_iteration(iteration_id: int, db: Session = Depends(get_db)):
    return _serialize_iteration(_get_iteration(db, iteration_id))


@router.post("/iterations/{iteration_id}/approve", response_model=RsiIterationResponse)
def approve_iteration_route(
    iteration_id: int,
    payload: RsiApproveRequest | None = None,
    db: Session = Depends(get_db),
):
    request = payload or RsiApproveRequest()
    try:
        iteration = approve_iteration(
            db,
            iteration_id,
            actor=request.actor,
            resume=request.resume,
        )
    except (LookupError, RsiStateError, ValueError) as exc:
        _raise_http(exc)
        raise  # pragma: no cover - _raise_http always raises
    loop = db.query(RsiLoop).filter(RsiLoop.id == iteration.loop_id).first()
    if request.resume and loop is not None and loop.status == "running":
        launch_rsi_loop(loop.id)
    return _serialize_iteration(_get_iteration(db, iteration.id))


@router.post("/iterations/{iteration_id}/reject", response_model=RsiIterationResponse)
def reject_iteration_route(
    iteration_id: int,
    payload: RsiRejectRequest | None = None,
    db: Session = Depends(get_db),
):
    request = payload or RsiRejectRequest(reason="人工驳回")
    try:
        iteration = reject_iteration(
            db,
            iteration_id,
            reason=request.reason,
            actor=request.actor,
            resume=request.resume,
        )
    except (LookupError, RsiStateError, ValueError) as exc:
        _raise_http(exc)
        raise  # pragma: no cover
    loop = db.query(RsiLoop).filter(RsiLoop.id == iteration.loop_id).first()
    if request.resume and loop is not None and loop.status == "running":
        launch_rsi_loop(loop.id)
    return _serialize_iteration(_get_iteration(db, iteration.id))


@router.post("/loops/{loop_id}/rollback", response_model=RsiRollbackResponse)
def rollback_loop_route(
    loop_id: int,
    payload: RsiRollbackRequest,
    db: Session = Depends(get_db),
):
    loop = _get_loop(db, loop_id)
    try:
        rolled = rollback_loop(
            db,
            loop,
            version_id=payload.version_id,
            iteration_id=payload.iteration_id,
            actor=payload.actor,
        )
    except (LookupError, RsiStateError, ValueError) as exc:
        _raise_http(exc)
        raise  # pragma: no cover
    return RsiRollbackResponse(
        rolled_back_version_ids=rolled,
        loop_id=loop.id,
        message=f"已回滚 {len(rolled)} 个配置版本",
    )


@router.get("/loops/{loop_id}/versions", response_model=RsiVersionListResponse)
def list_loop_versions(loop_id: int, db: Session = Depends(get_db)):
    _get_loop(db, loop_id)
    versions = (
        db.query(RsiConfigVersion)
        .filter(RsiConfigVersion.loop_id == loop_id)
        .order_by(RsiConfigVersion.id.desc())
        .all()
    )
    return RsiVersionListResponse(
        total=len(versions),
        items=[_serialize_version(item) for item in versions],
    )


@router.get(
    "/configs/{scope}/{scope_id}/versions",
    response_model=RsiVersionListResponse,
)
def list_versions(
    scope: str,
    scope_id: int,
    db: Session = Depends(get_db),
):
    if scope not in VERSION_SCOPES:
        raise HTTPException(status_code=400, detail=f"不支持的配置 scope: {scope}")
    versions = (
        db.query(RsiConfigVersion)
        .filter(
            RsiConfigVersion.scope == scope,
            RsiConfigVersion.scope_id == scope_id,
        )
        .order_by(RsiConfigVersion.version.desc())
        .all()
    )
    return RsiVersionListResponse(
        total=len(versions),
        items=[_serialize_version(item) for item in versions],
    )


@router.post(
    "/configs/versions/{version_id}/restore",
    response_model=RsiConfigVersionResponse,
)
def restore_version_route(
    version_id: int,
    actor: str | None = Query(None),
    db: Session = Depends(get_db),
):
    try:
        version = restore_version(db, version_id, actor=actor or "human")
        db.commit()
        db.refresh(version)
    except ValueError as exc:
        message = str(exc)
        code = 404 if "不存在" in message else 400
        raise HTTPException(status_code=code, detail=message) from exc
    return _serialize_version(version)


@router.post("/proposals/{proposal_id}/preview", response_model=RsiPreviewResponse)
async def preview_proposal(
    proposal_id: int,
    request: RsiPreviewRequest,
    db: Session = Depends(get_db),
):
    proposal = db.query(RsiProposal).filter(RsiProposal.id == proposal_id).first()
    if proposal is None:
        raise HTTPException(status_code=404, detail="RSI 提案不存在")
    iteration = _get_iteration(db, proposal.iteration_id)
    loop = _get_loop(db, iteration.loop_id)
    baseline = db.query(EvalTask).filter(EvalTask.id == loop.baseline_eval_id).first()
    snapshot = (baseline.scenario_snapshot or {}) if baseline is not None else {}
    if not snapshot:
        raise HTTPException(status_code=400, detail="基线评估缺少 scenario_snapshot，无法预览")

    candidates = [item for item in iteration.proposals if item.status == "validated"]
    if not candidates:
        candidates = [proposal]
    try:
        candidate_snapshot = build_candidate_snapshot_for_loop(
            loop, iteration, candidates, snapshot
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    endpoint_config = (
        candidate_endpoint_config(loop, candidates)
        if loop.evaluation_mode == "endpoint"
        else None
    )
    payload = EvalDebugRequest(
        name="RSI 沙盒预览",
        dataset_id=loop.dataset_id,
        scenario_id=loop.scenario_id,
        llm_config_id=loop.llm_config_id,
        evaluation_mode=loop.evaluation_mode or "offline",
        endpoint_target_id=loop.endpoint_target_id,
        target_config=endpoint_config if endpoint_config is not None else loop.target_config,
        response_mapping=loop.response_mapping,
        result_save_mode="task_only",
        row_id=request.row_id,
    )
    result = await run_debug_evaluation(db, payload, scenario_snapshot=candidate_snapshot)
    return RsiPreviewResponse(
        success=result.success,
        message=result.message,
        row_id=result.dataset_row.id if result.dataset_row is not None else request.row_id,
        row_data=result.row_data,
        metric_scores=result.metric_scores,
        is_pass=result.is_pass,
        warnings=result.warnings,
        errors=result.errors,
    )


@router.get("/loops/{loop_id}/compare", response_model=RsiCompareResponse)
def compare_iteration(
    loop_id: int,
    iteration_id: int | None = Query(None),
    db: Session = Depends(get_db),
):
    loop = _get_loop(db, loop_id)
    if iteration_id is not None:
        iteration = (
            db.query(RsiIteration)
            .filter(
                RsiIteration.id == iteration_id,
                RsiIteration.loop_id == loop.id,
            )
            .first()
        )
        if iteration is None:
            raise HTTPException(status_code=404, detail="RSI 迭代不存在")
    elif loop.best_iteration_id:
        iteration = (
            db.query(RsiIteration)
            .filter(RsiIteration.id == loop.best_iteration_id)
            .first()
        )
        if iteration is None:
            raise HTTPException(status_code=404, detail="最佳迭代不存在")
    else:
        iteration = _latest_iteration(db, loop.id)
        if iteration is None:
            raise HTTPException(status_code=404, detail="循环尚无迭代记录")

    metrics = iteration.metrics or {}
    decision = metrics.get("decision_metrics") or {}
    return RsiCompareResponse(
        loop_id=loop.id,
        iteration_id=iteration.id,
        baseline_eval_id=iteration.baseline_eval_id,
        candidate_eval_id=iteration.candidate_eval_id,
        objective_mode=loop.objective_mode,
        objective_metric=loop.objective_metric,
        decision=decision.get("decision") or iteration.decision,
        decision_reason=str(decision.get("reason") or iteration.decision_reason or "") or None,
        full={
            "baseline": metrics.get("baseline"),
            "candidate": metrics.get("candidate"),
            "delta": metrics.get("delta"),
        },
        train=metrics.get("train") or {},
        holdout=metrics.get("holdout") or {},
    )


@router.post("/loops/{loop_id}/hard-cases", response_model=RsiHardCaseResponse)
def create_hard_cases(
    loop_id: int,
    payload: RsiHardCaseRequest,
    db: Session = Depends(get_db),
):
    loop = _get_loop(db, loop_id)
    iteration = _latest_iteration(db, loop.id)
    try:
        result = create_hard_case_dataset(
            db,
            loop,
            row_ids=payload.row_ids,
            iteration_id=iteration.id if iteration is not None else None,
            name=payload.name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RsiHardCaseResponse(**result)
