from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./eval_platform.db"
    UPLOAD_DIR: str = "./uploads"
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]
    SEED_ON_STARTUP: bool = True
    RUN_EVAL_ON_CREATE: bool = True

    DEFAULT_LLM_NAME: str = "Qwen Plus (通义千问)"
    LLM_PROVIDER: str = "openai"
    LLM_ENDPOINT: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    LLM_MODEL: str = "qwen-plus"
    LLM_API_KEY: str = ""
    LLM_TEMPERATURE: float = 0.01
    LLM_MAX_TOKENS: int = 1024

    # RSI (evaluation-driven config self-evolution). Defaults keep the feature
    # usable on a fresh install while every safety knob stays configurable.
    RSI_ENABLED: bool = True
    RSI_MAX_ITERATIONS: int = 3
    RSI_MAX_ROWS_PER_ITERATION: int = 50
    RSI_MAX_LLM_CALLS: int = 300
    RSI_MAX_MINUTES: int = 45
    RSI_MAX_PROPOSALS_PER_ITERATION: int = 3
    RSI_HOLDOUT_RATIO: float = 0.3
    RSI_HOLDOUT_MIN_ROWS: int = 10
    RSI_HOLDOUT_MIN_ROWS_AUTO: int = 30
    RSI_MIN_OBJECTIVE_GAIN: float = 0.03
    RSI_MAX_METRIC_DROP: float = 0.02
    RSI_MAX_ERROR_RATE_DELTA: float = 0.02
    RSI_MAX_JUDGE_DRIFT: float = 0.15
    RSI_AUTO_APPLY_LOW_RISK: bool = False
    RSI_PROPOSER_TEMPERATURE: float = 0.2

    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
