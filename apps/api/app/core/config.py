from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "AutoPrep AI API"
    environment: str = "dev"
    database_url: str = "postgresql+psycopg2://autoprep:autoprep@postgres:5432/autoprep"
    redis_url: str = "redis://redis:6379/0"
    openai_api_key: str | None = None
    gemini_api_key: str | None = None
    
    # Storage
    storage_backend: str = "local"  # local, s3, gcs, azure
    storage_path: str = "./storage"
    
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