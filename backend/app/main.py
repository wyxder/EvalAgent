import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.core.config import settings
from app.core.database import engine, Base, ensure_runtime_schema
from app.core.errors import register_exception_handlers
from app.core.observability import RequestContextMiddleware, configure_logging
from app.core.rate_limit import RateLimitMiddleware


def _configure_app_logging() -> None:
    """Configure project logging with request ids and optional JSON output."""

    configure_logging(
        level_name=os.getenv("APP_LOG_LEVEL", settings.LOG_LEVEL),
        json_mode=settings.LOG_JSON,
    )


_configure_app_logging()

# Import all models so they register with Base before create_all
import app.models  # noqa: F401


@asynccontextmanager
async def lifespan(application: FastAPI):
    # Startup: create all tables
    Base.metadata.create_all(bind=engine)
    ensure_runtime_schema()

    # Ensure upload directory exists
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    if settings.SEED_ON_STARTUP:
        # Run seed data (import here to avoid circular imports)
        from app.seed import run_seed
        from app.core.database import SessionLocal
        db = SessionLocal()
        try:
            run_seed(db)
        finally:
            db.close()

    _backfill_eval_task_scenario_snapshots()

    yield

    # Shutdown: nothing to clean up for now


def _backfill_eval_task_scenario_snapshots() -> None:
    """Freeze current scenario configs for historical tasks created before snapshots."""

    from sqlalchemy.orm import joinedload

    from app.core.database import SessionLocal
    from app.core.scenario_snapshot import build_scenario_snapshot
    from app.models.evaluation import EvalTask
    from app.models.scenario import EvalScenario, ScenarioMetric

    db = SessionLocal()
    try:
        tasks = (
            db.query(EvalTask)
            .filter(EvalTask.scenario_snapshot.is_(None))
            .all()
        )
        if not tasks:
            return

        scenario_ids = {task.scenario_id for task in tasks}
        scenarios = (
            db.query(EvalScenario)
            .options(
                joinedload(EvalScenario.metrics).joinedload(ScenarioMetric.metric_definition)
            )
            .filter(EvalScenario.id.in_(scenario_ids))
            .all()
        )
        scenario_by_id = {scenario.id: scenario for scenario in scenarios}
        for task in tasks:
            scenario = scenario_by_id.get(task.scenario_id)
            if scenario is not None:
                task.scenario_snapshot = build_scenario_snapshot(scenario)
        db.commit()
    finally:
        db.close()


app = FastAPI(
    title="AI Evaluation Platform",
    description="Backend API for the AI Evaluation Platform",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(
    RateLimitMiddleware,
    enabled=settings.RATE_LIMIT_ENABLED,
    limit_per_minute=settings.RATE_LIMIT_HEAVY_PER_MIN,
)
app.add_middleware(RequestContextMiddleware)
register_exception_handlers(app)

# Import and include routers
from app.api.llm_config import router as llm_config_router
from app.api.dataset import router as dataset_router
from app.api.metric import router as metric_router
from app.api.endpoint_target import router as endpoint_target_router
from app.api.scenario import router as scenario_router
from app.api.evaluation import router as evaluation_router
from app.api.report import router as report_router
from app.api.rag_dataset_job import router as rag_dataset_job_router
from app.api.blind_test import router as blind_test_router
from app.api.rsi import router as rsi_router
from app.api.audit import router as audit_router

app.include_router(llm_config_router, prefix="/api")
app.include_router(dataset_router, prefix="/api")
app.include_router(metric_router, prefix="/api")
app.include_router(endpoint_target_router, prefix="/api")
app.include_router(scenario_router, prefix="/api")
app.include_router(evaluation_router, prefix="/api")
app.include_router(report_router, prefix="/api")
app.include_router(rag_dataset_job_router, prefix="/api")
app.include_router(blind_test_router, prefix="/api")
app.include_router(rsi_router, prefix="/api")
app.include_router(audit_router, prefix="/api")

# Static file serving for uploads
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}


@app.get("/api/ready")
async def readiness_check():
    """Readiness probe: database connectivity + a usable Judge model config."""

    checks: dict[str, str] = {}
    ready = True

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {exc}"
        ready = False

    try:
        from app.core.database import SessionLocal
        from app.models.llm_config import LLMConfig

        db = SessionLocal()
        try:
            config_count = db.query(LLMConfig).count()
        finally:
            db.close()

        if config_count == 0 and not settings.LLM_API_KEY:
            checks["judge_model"] = "missing: 未配置任何 LLM 配置且 LLM_API_KEY 为空"
            ready = False
        else:
            checks["judge_model"] = f"ok: {config_count} 个配置"
    except Exception as exc:
        checks["judge_model"] = f"error: {exc}"
        ready = False

    checks["upload_dir"] = "ok" if os.path.isdir(settings.UPLOAD_DIR) else "missing"
    payload = {"status": "ready" if ready else "not_ready", "checks": checks}
    return JSONResponse(status_code=200 if ready else 503, content=payload)
