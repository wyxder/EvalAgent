"""RSI (evaluation-driven config self-evolution) persistence models.

Design notes:
- ``rsi_loops`` / ``rsi_iterations`` are linked to ``eval_tasks`` by plain
  integer columns on both sides. Declaring ``eval_tasks.rsi_loop_id`` as a real
  foreign key would create a DDL cycle (eval_tasks -> rsi_loops -> eval_tasks)
  that SQLite cannot resolve with ``ALTER TABLE``, so the audit links stay
  unenforced integers. This keeps old databases patchable via
  ``ensure_runtime_schema()``.
- ``rsi_config_versions`` is append-only: rows are never updated except for the
  ``rolled_back_at`` marker, which keeps the audit trail immutable.
"""

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class RsiLoop(Base):
    """One self-evolution loop, anchored on a completed baseline evaluation."""

    __tablename__ = "rsi_loops"
    __table_args__ = (
        Index("ix_rsi_loops_status_created", "status", "created_at"),
        Index("ix_rsi_loops_baseline_eval", "baseline_eval_id"),
        Index("ix_rsi_loops_scenario", "scenario_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(50), default="draft", nullable=False)
    baseline_eval_id = Column(Integer, ForeignKey("eval_tasks.id"), nullable=False)
    dataset_id = Column(Integer, ForeignKey("datasets.id"), nullable=False)
    scenario_id = Column(Integer, ForeignKey("eval_scenarios.id"), nullable=False)
    llm_config_id = Column(Integer, ForeignKey("llm_configs.id"), nullable=False)
    proposer_llm_config_id = Column(Integer, ForeignKey("llm_configs.id"), nullable=True)
    evaluation_mode = Column(String(50), default="offline")
    endpoint_target_id = Column(Integer, ForeignKey("endpoint_targets.id"), nullable=True)
    target_config = Column(JSON, nullable=True)
    response_mapping = Column(JSON, nullable=True)
    result_save_mode = Column(String(50), default="task_only")
    objective_metric = Column(String(100), nullable=True)
    objective_target = Column(Float, nullable=True)
    objective_mode = Column(String(30), default="reference_pass_rate")
    reference_thresholds = Column(JSON, nullable=True)
    holdout_config = Column(JSON, nullable=True)
    acceptance_policy = Column(JSON, nullable=True)
    budget = Column(JSON, nullable=True)
    usage = Column(JSON, nullable=True)
    current_iteration = Column(Integer, default=0)
    best_iteration_id = Column(Integer, nullable=True)
    final_eval_id = Column(Integer, nullable=True)
    auto_apply_low_risk = Column(Boolean, default=False)
    error_message = Column(Text, nullable=True)
    logs = Column(Text, default="")
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    iterations = relationship(
        "RsiIteration",
        back_populates="loop",
        cascade="all, delete-orphan",
        order_by="RsiIteration.iteration_index",
    )
    dataset = relationship("Dataset", foreign_keys=[dataset_id])
    scenario = relationship("EvalScenario", foreign_keys=[scenario_id])
    llm_config = relationship("LLMConfig", foreign_keys=[llm_config_id])
    proposer_llm_config = relationship("LLMConfig", foreign_keys=[proposer_llm_config_id])
    baseline_eval = relationship("EvalTask", foreign_keys=[baseline_eval_id])


class RsiIteration(Base):
    """One diagnose -> propose -> regression -> decide cycle."""

    __tablename__ = "rsi_iterations"
    __table_args__ = (
        UniqueConstraint("loop_id", "iteration_index", name="uq_rsi_iteration_index"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    loop_id = Column(Integer, ForeignKey("rsi_loops.id", ondelete="CASCADE"), nullable=False)
    iteration_index = Column(Integer, nullable=False)
    status = Column(String(50), default="pending", nullable=False)
    baseline_eval_id = Column(Integer, nullable=True)
    candidate_eval_id = Column(Integer, nullable=True)
    diagnosis = Column(JSON, nullable=True)
    metrics = Column(JSON, nullable=True)
    proposal_count = Column(Integer, default=0)
    decision = Column(String(50), nullable=True)
    decision_reason = Column(Text, nullable=True)
    cost = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now())

    loop = relationship("RsiLoop", back_populates="iterations")
    proposals = relationship(
        "RsiProposal",
        back_populates="iteration",
        cascade="all, delete-orphan",
        order_by="RsiProposal.id",
    )


class RsiProposal(Base):
    """A single whitelisted configuration patch proposed by the proposer LLM."""

    __tablename__ = "rsi_proposals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    loop_id = Column(Integer, ForeignKey("rsi_loops.id", ondelete="CASCADE"), nullable=False)
    iteration_id = Column(Integer, ForeignKey("rsi_iterations.id", ondelete="CASCADE"), nullable=False)
    target_type = Column(String(50), nullable=False)
    target_id = Column(Integer, nullable=True)
    field = Column(String(100), nullable=False)
    operation = Column(String(20), default="set", nullable=False)
    before_value = Column(JSON, nullable=True)
    after_value = Column(JSON, nullable=True)
    rationale = Column(Text, nullable=True)
    evidence = Column(JSON, nullable=True)
    risk_level = Column(String(20), default="medium")
    requires_review = Column(Boolean, default=True)
    status = Column(String(30), default="proposed", nullable=False)
    applied_version_id = Column(Integer, nullable=True)
    decided_by = Column(String(50), nullable=True)
    decided_at = Column(DateTime, nullable=True)
    decision_source = Column(String(30), nullable=True)
    created_at = Column(DateTime, default=func.now())
    applied_at = Column(DateTime, nullable=True)

    iteration = relationship("RsiIteration", back_populates="proposals")


class RsiConfigVersion(Base):
    """Immutable snapshot of a platform config entity taken right before write-back."""

    __tablename__ = "rsi_config_versions"
    __table_args__ = (
        UniqueConstraint("scope", "scope_id", "version", name="uq_rsi_config_version"),
        Index("ix_rsi_config_versions_iteration", "loop_id", "iteration_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    loop_id = Column(Integer, nullable=True)
    iteration_id = Column(Integer, nullable=True)
    proposal_id = Column(Integer, nullable=True)
    scope = Column(String(50), nullable=False)
    scope_id = Column(Integer, nullable=False)
    version = Column(Integer, nullable=False)
    snapshot = Column(JSON, nullable=False)
    patch = Column(JSON, nullable=True)
    parent_version_id = Column(Integer, nullable=True)
    actor = Column(String(50), default="system")
    created_at = Column(DateTime, default=func.now())
    rolled_back_at = Column(DateTime, nullable=True)
