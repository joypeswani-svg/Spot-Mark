"""
config.py — TruthLens Backend Configuration

All settings are read from environment variables.
API keys NEVER have defaults here — they must be set in .env or the environment.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Server ────────────────────────────────────────────────────────────────
    ENVIRONMENT: str = "development"
    # Comma-separated origins. In dev mode, all origins are allowed automatically.
    # In production, restrict to your actual frontend URLs and extension IDs.
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8000"
    # When True (dev), allows ALL origins including chrome-extension:// URLs
    ALLOW_ALL_ORIGINS_IN_DEV: bool = True

    # ── Database ──────────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://truthlens:truthlens_dev_password@localhost:5432/truthlens"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 5

    # ── Redis ─────────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    CACHE_TTL_SECONDS: int = 86400  # 24 hours

    # ── LLM ──────────────────────────────────────────────────────────────────
    GEMINI_API_KEY: str = ""          # Set in .env — no default
    GEMINI_MODEL: str = "gemini-3.6-flash"
    # Fallback when Gemini is unavailable or quota exhausted
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.1:8b"
    # LM Studio: OpenAI-compatible local LLM server (use 127.0.0.1 to avoid Windows IPv6 resolution drops)
    LMSTUDIO_BASE_URL: str = "http://127.0.0.1:1234/v1"
    LMSTUDIO_MODEL: str = "qwen3-8b"
    # Groq API: Ultra-fast LPU inference (Llama 3.3 70B free tier)
    GROQ_API_KEY: str = ""             # Set in .env
    GROQ_MODEL: str = "qwen/qwen3.6-27b"
    LLM_PROVIDER: str = "groq"         # "groq" | "gemini" | "lmstudio" | "ollama"

    # ── External APIs ─────────────────────────────────────────────────────────
    GOOGLE_FACT_CHECK_API_KEY: str = ""
    GOOGLE_VISION_API_KEY: str = ""
    # GDELT: no API key needed (open)
    GDELT_BASE_URL: str = "https://api.gdeltproject.org/api/v2"

    # ── Auth ──────────────────────────────────────────────────────────────────
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""  # Server-side only, NEVER exposed to clients

    # ── ML Models ─────────────────────────────────────────────────────────────
    # Deepfake detection provider adapter
    # "local" = self-hosted HuggingFace model (default, free)
    # "hive"  = Hive Moderation API (paid upgrade)
    # "sensity" = Sensity.ai API (paid upgrade)
    DEEPFAKE_PROVIDER: str = "local"
    HIVE_API_KEY: str = ""            # Only needed if DEEPFAKE_PROVIDER=hive
    SENSITY_API_KEY: str = ""         # Only needed if DEEPFAKE_PROVIDER=sensity

    # Embedding model (local, no API key needed)
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DIM: int = 384

    # DistilBERT ONNX fast classifier
    STYLE_CLASSIFIER_PATH: str = "ml/models/distilbert_fakenews.onnx"

    # ── Scoring weights ───────────────────────────────────────────────────────
    SCORE_WEIGHT_CLAIM_VERIFICATION: float = 0.50
    SCORE_WEIGHT_DOMAIN_REPUTATION:  float = 0.20
    SCORE_WEIGHT_STYLE_CLASSIFIER:   float = 0.15
    SCORE_WEIGHT_CROSS_CORROBORATION: float = 0.15

    # ── Credibility bands ─────────────────────────────────────────────────────
    BAND_GREEN_MIN:  int = 80   # 80–100: Verified
    BAND_YELLOW_MIN: int = 50   # 50–79: Caution
    # 0–49: Likely False/Unverified


settings = Settings()
