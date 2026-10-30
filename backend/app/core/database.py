from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker, declarative_base

from app.core.config import settings

database_url = make_url(settings.DATABASE_URL)
engine_options = {"pool_pre_ping": True}
if database_url.drivername.startswith("sqlite"):
    engine_options["connect_args"] = {"check_same_thread": False}

engine = create_engine(settings.DATABASE_URL, **engine_options)


if database_url.drivername.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def ensure_runtime_schema() -> None:
    """Apply tiny SQLite-compatible schema additions for existing local DBs."""

    if not engine.dialect.name.startswith("sqlite"):
        return

    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    if "eval_tasks" not in table_names:
        return

    eval_task_columns = {column["name"] for column in inspector.get_columns("eval_tasks")}
    eval_task_additions = {
        "scenario_snapshot": "ALTER TABLE eval_tasks ADD COLUMN scenario_snapshot JSON",
        "evaluation_mode": "ALTER TABLE eval_tasks ADD COLUMN evaluation_mode VARCHAR(50) DEFAULT 'offline'",
        "endpoint_target_id": "ALTER TABLE eval_tasks ADD COLUMN endpoint_target_id INTEGER",
        "target_config": "ALTER TABLE eval_tasks ADD COLUMN target_config JSON",
        "response_mapping": "ALTER TABLE eval_tasks ADD COLUMN response_mapping JSON",
        "result_save_mode": "ALTER TABLE eval_tasks ADD COLUMN result_save_mode VARCHAR(50) DEFAULT 'task_only'",
        "rsi_loop_id": "ALTER TABLE eval_tasks ADD COLUMN rsi_loop_id INTEGER",
        "rsi_iteration_id": "ALTER TABLE eval_tasks ADD COLUMN rsi_iteration_id INTEGER",
        "token_usage": "ALTER TABLE eval_tasks ADD COLUMN token_usage JSON",
        "prompt_version": "ALTER TABLE eval_tasks ADD COLUMN prompt_version VARCHAR(50)",
    }
    missing_eval_task_sql = [
        sql for name, sql in eval_task_additions.items() if name not in eval_task_columns
    ]
    if missing_eval_task_sql:
        with engine.begin() as connection:
            for sql in missing_eval_task_sql:
                connection.execute(text(sql))

    if "rag_dataset_jobs" in table_names:
        rag_job_columns = {column["name"] for column in inspector.get_columns("rag_dataset_jobs")}
        additions = {
            "target_endpoint_url": "ALTER TABLE rag_dataset_jobs ADD COLUMN target_endpoint_url VARCHAR(1000)",
            "target_transport_mode": "ALTER TABLE rag_dataset_jobs ADD COLUMN target_transport_mode VARCHAR(50) DEFAULT 'sse'",
            "target_authorization": "ALTER TABLE rag_dataset_jobs ADD COLUMN target_authorization TEXT",
            "target_extra_headers": "ALTER TABLE rag_dataset_jobs ADD COLUMN target_extra_headers TEXT",
            "target_request_body_template": "ALTER TABLE rag_dataset_jobs ADD COLUMN target_request_body_template TEXT",
        }
        missing_sql = [sql for name, sql in additions.items() if name not in rag_job_columns]
        if missing_sql:
            with engine.begin() as connection:
                for sql in missing_sql:
                    connection.execute(text(sql))

    if "eval_row_results" in table_names:
        row_result_columns = {column["name"] for column in inspector.get_columns("eval_row_results")}
        additions = {
            "manual_status": "ALTER TABLE eval_row_results ADD COLUMN manual_status VARCHAR(50)",
            "manual_score": "ALTER TABLE eval_row_results ADD COLUMN manual_score FLOAT",
            "manual_tags": "ALTER TABLE eval_row_results ADD COLUMN manual_tags JSON",
            "manual_note": "ALTER TABLE eval_row_results ADD COLUMN manual_note TEXT",
            "reviewed_at": "ALTER TABLE eval_row_results ADD COLUMN reviewed_at DATETIME",
            "endpoint_trace": "ALTER TABLE eval_row_results ADD COLUMN endpoint_trace JSON",
        }
        missing_sql = [sql for name, sql in additions.items() if name not in row_result_columns]
        if missing_sql:
            with engine.begin() as connection:
                for sql in missing_sql:
                    connection.execute(text(sql))

    if "scenario_metrics" in table_names:
        scenario_metric_columns = {column["name"] for column in inspector.get_columns("scenario_metrics")}
        if "prompt_override" not in scenario_metric_columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE scenario_metrics ADD COLUMN prompt_override TEXT"))

    _ensure_indexes(table_names)


def _ensure_indexes(table_names: list[str]) -> None:
    """Create indexes for databases that were built before ``index=True`` columns."""

    index_specs: list[tuple[str, str, str]] = [
        ("eval_tasks", "ix_eval_tasks_dataset_id", "dataset_id"),
        ("eval_tasks", "ix_eval_tasks_scenario_id", "scenario_id"),
        ("eval_tasks", "ix_eval_tasks_llm_config_id", "llm_config_id"),
        ("eval_tasks", "ix_eval_tasks_status", "status"),
        ("eval_tasks", "ix_eval_tasks_created_at", "created_at"),
        ("eval_row_results", "ix_eval_row_results_eval_task_id", "eval_task_id"),
        ("eval_row_results", "ix_eval_row_results_dataset_row_id", "dataset_row_id"),
        ("eval_row_results", "ix_eval_row_results_task_row", "eval_task_id, row_index"),
        ("dataset_rows", "ix_dataset_rows_dataset_id", "dataset_id"),
        ("dataset_rows", "ix_dataset_rows_dataset_row", "dataset_id, row_index"),
        ("scenario_metrics", "ix_scenario_metrics_scenario_id", "scenario_id"),
        (
            "scenario_metrics",
            "ix_scenario_metrics_metric_definition_id",
            "metric_definition_id",
        ),
    ]
    with engine.begin() as connection:
        for table, index_name, columns in index_specs:
            if table not in table_names:
                continue
            connection.execute(
                text(
                    f"CREATE INDEX IF NOT EXISTS {index_name} ON {table} ({columns})"
                )
            )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
