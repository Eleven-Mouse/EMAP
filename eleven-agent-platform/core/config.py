import os
from pathlib import Path


def _load_dotenv_file() -> None:
    root = Path(__file__).resolve().parents[2]
    env_file = root / ".env"
    if not env_file.exists():
        return

    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv_file()


def _to_int(value: str, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_float(value: str, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_bool(value: str, default: bool) -> bool:
    if value is None:
        return default
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


class Settings:
    def __init__(self) -> None:
        self.app_name = os.getenv("APP_NAME", "Eleven Memory Agent Platform")
        self.app_env = os.getenv("APP_ENV", "dev")
        self.top_k = _to_int(os.getenv("TOP_K", "5"), 5)
        self.chunk_size = _to_int(os.getenv("CHUNK_SIZE", "500"), 500)
        self.chunk_overlap = _to_int(os.getenv("CHUNK_OVERLAP", "100"), 100)
        self.rag_store_dir = os.getenv("RAG_STORE_DIR", ".rag_store")
        self.embedding_model_name = os.getenv(
            "EMBEDDING_MODEL_NAME", "BAAI/bge-m3"
        )
        self.embedding_device = os.getenv("EMBEDDING_DEVICE", "cpu")
        self.embedding_cache_dir = os.getenv(
            "EMBEDDING_CACHE_DIR", f"{self.rag_store_dir}/models"
        )
        self.llm_enabled = _to_bool(os.getenv("LLM_ENABLED", "false"), False)
        self.llm_api_base = os.getenv("LLM_API_BASE", "").rstrip("/")
        self.llm_api_key = os.getenv("LLM_API_KEY", "")
        self.llm_model = os.getenv("LLM_MODEL", "mimo-pro")
        self.llm_temperature = _to_float(os.getenv("LLM_TEMPERATURE", "0.2"), 0.2)
        self.llm_max_tokens = _to_int(os.getenv("LLM_MAX_TOKENS", "1024"), 1024)
        self.llm_timeout_seconds = _to_int(
            os.getenv("LLM_TIMEOUT_SECONDS", "60"),
            60,
        )
        self.mysql_dsn = os.getenv(
            "MYSQL_DSN",
            "mysql+pymysql://root:password@127.0.0.1:3306/eleven_rag?charset=utf8mb4",
        )
        self.mysql_pool_size = _to_int(os.getenv("MYSQL_POOL_SIZE", "5"), 5)
        self.mysql_max_overflow = _to_int(os.getenv("MYSQL_MAX_OVERFLOW", "10"), 10)
        self.mysql_pool_recycle_seconds = _to_int(
            os.getenv("MYSQL_POOL_RECYCLE_SECONDS", "3600"), 3600
        )
        self.mysql_pool_timeout_seconds = _to_int(
            os.getenv("MYSQL_POOL_TIMEOUT_SECONDS", "30"), 30
        )
        self.mysql_retry_attempts = _to_int(os.getenv("MYSQL_RETRY_ATTEMPTS", "3"), 3)
        self.mysql_retry_backoff_seconds = _to_float(
            os.getenv("MYSQL_RETRY_BACKOFF_SECONDS", "0.2"), 0.2
        )
        self.memory_retry_attempts = _to_int(
            os.getenv("MEMORY_RETRY_ATTEMPTS", str(self.mysql_retry_attempts)),
            self.mysql_retry_attempts,
        )
        self.memory_retry_backoff_seconds = _to_float(
            os.getenv(
                "MEMORY_RETRY_BACKOFF_SECONDS",
                str(self.mysql_retry_backoff_seconds),
            ),
            self.mysql_retry_backoff_seconds,
        )
        self.memory_op_alert_threshold_ms = _to_int(
            os.getenv("MEMORY_OP_ALERT_THRESHOLD_MS", "200"),
            200,
        )
        self.memory_failure_alert_threshold = _to_int(
            os.getenv("MEMORY_FAILURE_ALERT_THRESHOLD", "3"),
            3,
        )
        self.memory_monitor_enabled = _to_bool(
            os.getenv("MEMORY_MONITOR_ENABLED", "true"),
            True,
        )
        self.redis_url = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
        self.session_ttl_seconds = _to_int(
            os.getenv("SESSION_TTL_SECONDS", "86400"), 86400
        )
        self.session_max_messages = _to_int(
            os.getenv("SESSION_MAX_MESSAGES", "100"), 100
        )
        self.summary_interval_rounds = _to_int(
            os.getenv("SUMMARY_INTERVAL_ROUNDS", "8"), 8
        )
        self.summary_window_messages = _to_int(
            os.getenv("SUMMARY_WINDOW_MESSAGES", "16"), 16
        )
        self.prompt_window_messages = _to_int(
            os.getenv("PROMPT_WINDOW_MESSAGES", "8"), 8
        )
        self.prompt_summary_max_items = _to_int(
            os.getenv("PROMPT_SUMMARY_MAX_ITEMS", "3"), 3
        )
        self.metadata_db_path = os.getenv(
            "METADATA_DB_PATH", f"{self.rag_store_dir}/metadata.db"
        )
        self.faiss_index_path = os.getenv(
            "FAISS_INDEX_PATH", f"{self.rag_store_dir}/faiss.index"
        )
        self.faiss_mapping_path = os.getenv(
            "FAISS_MAPPING_PATH", f"{self.rag_store_dir}/faiss_mapping.json"
        )
        self.vector_index_path = self.faiss_index_path


settings = Settings()
