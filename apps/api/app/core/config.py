from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "AutoPrep AI API"
    environment: str = "dev"
    gemini_api_key: str | None = None
    groq_api_key: str | None = None
    groq_model: str = "llama-3.3-70b-versatile"
    active_llm_provider: str = "gemini"  # gemini, groq
    identifier_missing_strategy: str = "flag_issue"  # flag_issue, remove_rows, leave_untouched
    outlier_strategy: str = "cap"  # cap, remove, flag

    # Storage
    storage_backend: str = "local"  # local
    storage_path: str = "./storage"
    session_expiration_minutes: int = 30
    delete_after_download: bool = True

    # Security
    secret_key: str = "dev-secret-key-change-in-production"
    max_upload_size_mb: int = 100

    # Observability
    log_level: str = "INFO"
    enable_tracing: bool = False

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()