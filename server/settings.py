import os
from datetime import timedelta
from typing import Optional


class Settings:
    """Centralized application settings with sensible defaults for Colab.

    Values can be overridden via environment variables when available.
    """

    # Base paths
    BASE_DIR: str = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    PUBLIC_DIR: str = os.path.join(BASE_DIR, "public")

    # Always default to project-local directories, override via env if needed
    UPLOAD_DIR: str = os.environ.get("UPLOAD_DIR", os.path.join(BASE_DIR, "uploads"))
    RESULTS_BASE_DIR: str = os.environ.get("RESULTS_BASE_DIR", os.path.join(PUBLIC_DIR, "temp-results"))

    # Server
    HOST: str = os.environ.get("HOST", "0.0.0.0")
    PORT: int = int(os.environ.get("PORT", "8888"))
    DISABLE_BACKGROUND: bool = os.environ.get("DISABLE_BACKGROUND", "false").lower() in {"1", "true", "yes"}

    # Concurrency and limits
    GLOBAL_CONCURRENCY: int = int(os.environ.get("GLOBAL_CONCURRENCY", "10"))
    PER_USER_CONCURRENCY: int = int(os.environ.get("PER_USER_CONCURRENCY", "10"))
    MAX_TASKS_PER_BATCH: int = int(os.environ.get("MAX_TASKS_PER_BATCH", "50"))
    MAX_BATCHES_PER_USER_PER_MINUTE: int = int(os.environ.get("MAX_BATCHES_PER_USER_PER_MINUTE", "10"))

    # Sessions
    SESSION_COOKIE_NAME: str = os.environ.get("SESSION_COOKIE_NAME", "session_id")
    SESSION_TTL: timedelta = timedelta(days=int(os.environ.get("SESSION_TTL_DAYS", "7")))

    # Idempotency window (seconds)
    IDEMPOTENCY_WINDOW_SECONDS: int = int(os.environ.get("IDEMPOTENCY_WINDOW_SECONDS", "60"))

    # Cleanup TTL (days)
    LOCAL_FILE_TTL_DAYS: int = int(os.environ.get("LOCAL_FILE_TTL_DAYS", "7"))

    # Image validation
    ALLOWED_IMAGE_MIME = {"image/png", "image/jpeg"}
    IMAGE_MAX_SIZE_MB: int = int(os.environ.get("IMAGE_MAX_SIZE_MB", "10"))
    IMAGE_MAX_EDGE_PX: int = int(os.environ.get("IMAGE_MAX_EDGE_PX", "4096"))

    # Crypto secret for API key encryption (Fernet-compatible 32 urlsafe bytes expected).
    # If not provided, a volatile in-memory key will be generated at runtime (not persistent).
    CRYPTO_SECRET: Optional[str] = os.environ.get("CRYPTO_SECRET")

    # Yunwu API settings (extensible provider configuration)
    YUNWU_API_BASE: str = os.environ.get("YUNWU_API_BASE", "https://yunwu.ai/v1")
    # Global fallback API key; preferred per-user key can be stored in DB
    YUNWU_API_KEY: Optional[str] = os.environ.get("YUNWU_API_KEY")
    # Public base URL for exposing local files (uploads) to external services (e.g., ngrok URL)
    PUBLIC_BASE_URL: Optional[str] = os.environ.get("PUBLIC_BASE_URL")
    # HTTP request configuration
    REQUEST_TIMEOUT_SECONDS: int = int(os.environ.get("REQUEST_TIMEOUT_SECONDS", "300"))
    DOWNLOAD_CHUNK_SIZE: int = int(os.environ.get("DOWNLOAD_CHUNK_SIZE", "8192"))
    POLL_INTERVAL_SECONDS: int = int(os.environ.get("POLL_INTERVAL_SECONDS", "3"))
    MAX_POLL_SECONDS: int = int(os.environ.get("MAX_POLL_SECONDS", "900"))  # 15 min


settings = Settings()

