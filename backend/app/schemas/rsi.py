"""Request/response contracts for the RSI self-evolution API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.sensitive import redact_sensitive_mapping


class RsiBudgetPayload(BaseModel):
    max_iterations: Optional[int] = Field(None, ge=1, le=10)
    max_rows_per_iteration: Optional[int] = Field(None, ge=1, le=500)
    max_llm_calls: Optional[int] = Field(None, ge=10, le=100000)
    max_minutes: Optional[int] = Field(None, ge=1, le=600)
    max_proposals_per_iteration: Optional[int] = Field(None, ge=1, le=3)
    max_consecutive_no_gain: Optional[int] = Field(None, ge=1, le=10)


class RsiSamplingPayload(BaseModel):
    holdout_ratio: Optional[float] = Field(None, ge=0, le=0.5)
    min_rows: Optional[int] = Field(None, ge=5)
    min_rows_for_auto_accept: Optional[int] = Field(None, ge=5)


class RsiObjectivePayload(BaseModel):
    metric: Optional[str] = None
    direction: Literal["maximize"] = "maximize"
    min_gain: Optional[float] = Field(None, ge=0, le=1)
    mode: Optional[Literal["metric_mean", "reference_pass_rate"]] = None


class RsiConstraintsPayload(BaseModel):
    max_metric_drop: Optional[float] = Field(None, ge=0, le=1)
    max_new_failures: Optional[int] = Field(None, ge=0)
    max_error_rate_delta: Optional[float] = Field(None, ge=0, le=1)
    protected_metrics: Optional[List[str]] = None


class RsiReviewPayload(BaseModel):
    auto_apply_low_risk: Optional[bool] = None
    require_human_for: Optional[List[str]] = None


class RsiAcceptancePolicyPayload(BaseModel):
    objective: Optional[RsiObjectivePayload] = None
    constraints: Optional[RsiConstraintsPayload] = None
    sampling: Optional[RsiSamplingPayload] = None
    review: Optional[RsiReviewPayload] = None


class RsiLoopCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    baseline_eval_id: int
    llm_config_id: Optional[int] = None
    proposer_llm_config_id: Optional[int] = None
    objective_metric: Optional[str] = None
    objective_mode: Literal["metric_mean", "reference_pass_rate"] = "reference_pass_rate"
    objective_target: Optional[float] = Field(None, ge=0, le=1)
    budget: Optional[RsiBudgetPayload] = None
    acceptance_policy: Optional[RsiAcceptancePolicyPayload] = None
    holdout: Optional[RsiSamplingPayload] = None
    auto_apply_low_risk: bool = False


class RsiLoopBrief(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    status: str
    baseline_eval_id: int
    dataset_id: int
    scenario_id: int
    llm_config_id: int
    proposer_llm_config_id: Optional[int] = None
    evaluation_mode: Optional[str] = "offline"
    endpoint_target_id: Optional[int] = None
    target_config: Optional[Dict[str, Any]] = None
    response_mapping: Optional[Dict[str, Any]] = None
    result_save_mode: Optional[str] = "task_only"
    objective_metric: Optional[str] = None
    objective_target: Optional[float] = None
    objective_mode: Optional[str] = None
    reference_thresholds: Optional[Dict[str, Any]] = None
    holdout_config: Optional[Dict[str, Any]] = None
    acceptance_policy: Optional[Dict[str, Any]] = None
    budget: Optional[Dict[str, Any]] = None
    usage: Optional[Dict[str, Any]] = None
    current_iteration: Optional[int] = 0
    best_iteration_id: Optional[int] = None
    final_eval_id: Optional[int] = None
    auto_apply_low_risk: bool = False
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def hide_target_secrets(self):
        self.target_config = redact_sensitive_mapping(self.target_config)
        return self


class RsiLoopResponse(RsiLoopBrief):
    dataset_name: Optional[str] = None
    scenario_name: Optional[str] = None
    llm_model_name: Optional[str] = None
    proposer_model_name: Optional[str] = None
    best_gain: Optional[float] = None
    best_iteration: Optional["RsiIterationBrief"] = None
    latest_iteration: Optional["RsiIterationBrief"] = None


class RsiProposalResponse(BaseModel):
    id: int
    loop_id: int
    iteration_id: int
    target_type: str
    target_id: Optional[int] = None
    field: str
    operation: str
    before_value: Any = None
    after_value: Any = None
    rationale: Optional[str] = None
    evidence: Optional[Dict[str, Any]] = None
    risk_level: Optional[str] = None
    requires_review: bool = True
    status: str
    applied_version_id: Optional[int] = None
    decided_by: Optional[str] = None
    decided_at: Optional[datetime] = None
    decision_source: Optional[str] = None
    created_at: Optional[datetime] = None
    applied_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class RsiIterationBrief(BaseModel):
    id: int
    loop_id: int
    iteration_index: int
    status: str
    baseline_eval_id: Optional[int] = None
    candidate_eval_id: Optional[int] = None
    proposal_count: int = 0
    objective_gain: Optional[float] = None
    holdout_pass_rate: Optional[float] = None
    cost: Optional[Dict[str, Any]] = None
    decision: Optional[str] = None
    decision_reason: Optional[str] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class RsiIterationResponse(RsiIterationBrief):
    diagnosis: Optional[Dict[str, Any]] = None
    metrics: Optional[Dict[str, Any]] = None
    cost: Optional[Dict[str, Any]] = None
    proposals: List[RsiProposalResponse] = []


class RsiIterationListResponse(BaseModel):
    total: int
    items: List[RsiIterationBrief]


class RsiLoopListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[RsiLoopResponse]


class RsiConfigVersionResponse(BaseModel):
    id: int
    loop_id: Optional[int] = None
    iteration_id: Optional[int] = None
    proposal_id: Optional[int] = None
    scope: str
    scope_id: int
    version: int
    snapshot: Optional[Dict[str, Any]] = None
    patch: Optional[Dict[str, Any]] = None
    parent_version_id: Optional[int] = None
    actor: Optional[str] = None
    created_at: Optional[datetime] = None
    rolled_back_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class RsiVersionListResponse(BaseModel):
    total: int
    items: List[RsiConfigVersionResponse]


class RsiLogsResponse(BaseModel):
    loop_id: int
    status: str
    current_iteration: int = 0
    logs: str = ""


class RsiApproveRequest(BaseModel):
    actor: Optional[str] = None
    resume: bool = True


class RsiRejectRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=2000)
    actor: Optional[str] = None
    resume: bool = False


class RsiRollbackRequest(BaseModel):
    version_id: Optional[int] = None
    iteration_id: Optional[int] = None
    actor: Optional[str] = None

    @model_validator(mode="after")
    def require_target(self):
        if self.version_id is None and self.iteration_id is None:
            raise ValueError("version_id 与 iteration_id 至少提供一个")
        return self


class RsiRollbackResponse(BaseModel):
    rolled_back_version_ids: List[int]
    loop_id: int
    message: str


class RsiPreviewRequest(BaseModel):
    row_id: Optional[int] = None


class RsiPreviewResponse(BaseModel):
    success: bool
    message: str
    row_id: Optional[int] = None
    row_data: Optional[Dict[str, Any]] = None
    metric_scores: Dict[str, Any] = {}
    is_pass: Optional[bool] = None
    warnings: List[str] = []
    errors: List[str] = []


class RsiHardCaseRequest(BaseModel):
    row_ids: List[int] = Field(default_factory=list)
    name: Optional[str] = None


class RsiHardCaseResponse(BaseModel):
    dataset_id: int
    dataset_name: str
    created_rows: int
    skipped_row_ids: List[int] = []


class RsiCompareResponse(BaseModel):
    loop_id: int
    iteration_id: int
    baseline_eval_id: Optional[int] = None
    candidate_eval_id: Optional[int] = None
    objective_mode: Optional[str] = None
    objective_metric: Optional[str] = None
    decision: Optional[str] = None
    decision_reason: Optional[str] = None
    full: Dict[str, Any] = {}
    train: Dict[str, Any] = {}
    holdout: Dict[str, Any] = {}


RsiLoopResponse.model_rebuild()
