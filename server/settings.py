import os
from datetime import timedelta
from typing import Optional

from dotenv import load_dotenv
load_dotenv()  # 加载 .env 文件


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

    # Aliyun SMS authentication service (SendSmsVerifyCode / CheckSmsVerifyCode)
    ALIYUN_SMS_ENDPOINT: str = os.environ.get("ALIYUN_SMS_ENDPOINT", "https://dypnsapi.aliyuncs.com")
    ALIYUN_SMS_REGION_ID: str = os.environ.get("ALIYUN_SMS_REGION_ID", "ap-southeast-1")
    ALIYUN_SMS_ACCESS_KEY_ID: Optional[str] = os.environ.get("ALIYUN_SMS_ACCESS_KEY_ID")
    ALIYUN_SMS_ACCESS_KEY_SECRET: Optional[str] = os.environ.get("ALIYUN_SMS_ACCESS_KEY_SECRET")
    ALIYUN_SMS_SIGN_NAME: Optional[str] = os.environ.get("ALIYUN_SMS_SIGN_NAME")
    ALIYUN_SMS_TEMPLATE_CODE: Optional[str] = os.environ.get("ALIYUN_SMS_TEMPLATE_CODE")
    SMS_CODE_EXPIRE_SECONDS: int = int(os.environ.get("SMS_CODE_EXPIRE_SECONDS", "300"))
    SMS_CODE_RESEND_INTERVAL: int = int(os.environ.get("SMS_CODE_RESEND_INTERVAL", "60"))
    SMS_CODE_MAX_PER_MOBILE_PER_DAY: int = int(os.environ.get("SMS_CODE_MAX_PER_MOBILE_PER_DAY", "15"))
    SMS_CODE_HASH_SALT: str = os.environ.get("SMS_CODE_HASH_SALT", "aliyun-sms-salt")

    # Payment
    ALIPAY_APP_ID: Optional[str] = os.environ.get("ALIPAY_APP_ID")
    ALIPAY_PRIVATE_KEY: Optional[str] = os.environ.get("ALIPAY_PRIVATE_KEY")
    ALIPAY_PUBLIC_KEY: Optional[str] = os.environ.get("ALIPAY_PUBLIC_KEY")

    WECHAT_PAY_APP_ID: Optional[str] = os.environ.get("WECHAT_PAY_APP_ID")
    WECHAT_PAY_MCH_ID: Optional[str] = os.environ.get("WECHAT_PAY_MCH_ID")
    WECHAT_PAY_APIV3_KEY: Optional[str] = os.environ.get("WECHAT_PAY_APIV3_KEY")
    WECHAT_PAY_CERT_SERIAL_NO: Optional[str] = os.environ.get("WECHAT_PAY_CERT_SERIAL_NO")
    WECHAT_PAY_PRIVATE_KEY: Optional[str] = os.environ.get("WECHAT_PAY_PRIVATE_KEY")

    # Google OAuth Settings
    # TODO: 填写你的 Google OAuth 凭据（从 Google Cloud Console 获取）
    # 1. 访问 https://console.cloud.google.com/apis/credentials
    # 2. 创建 OAuth 2.0 Client ID（Web application 类型）
    # 3. 添加授权重定向 URI: http://localhost:8888/api/auth/google/callback
    GOOGLE_CLIENT_ID: Optional[str] = os.environ.get("GOOGLE_CLIENT_ID", "")  # TODO: 填写
    GOOGLE_CLIENT_SECRET: Optional[str] = os.environ.get("GOOGLE_CLIENT_SECRET", "")  # TODO: 填写
    GOOGLE_REDIRECT_URI: str = os.environ.get("GOOGLE_REDIRECT_URI", "http://localhost:8888/api/auth/google/callback")

    # Stripe Payment Settings
    # TODO: 填写你的 Stripe 密钥（从 Stripe Dashboard 获取）
    # 1. 访问 https://dashboard.stripe.com/apikeys
    # 2. 获取 Publishable key 和 Secret key
    # 3. 配置 Webhook 后获取 Webhook Signing Secret
    STRIPE_SECRET_KEY: Optional[str] = os.environ.get("STRIPE_SECRET_KEY", "")  # TODO: 填写 sk_test_... 或 sk_live_...
    STRIPE_PUBLISHABLE_KEY: Optional[str] = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")  # TODO: 填写 pk_test_... 或 pk_live_...
    STRIPE_WEBHOOK_SECRET: Optional[str] = os.environ.get("STRIPE_WEBHOOK_SECRET", "")  # TODO: 填写 whsec_...

    @property
    def BASE_URL(self) -> str:
        return self.PUBLIC_BASE_URL or f"http://{self.HOST}:{self.PORT}"


settings = Settings()

