from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str
    redis_url: str
    rabbitmq_url: str

    r2_endpoint: str
    r2_access_key_id: str
    r2_secret_access_key: str
    r2_public_url_templates: str
    r2_public_url_results: str = ""
    r2_bucket_uploads: str = "uploads"
    r2_bucket_results: str = "results"
    r2_bucket_templates: str = "templates"

    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 43200
    refresh_token_expire_days: int = 30

    replicate_api_token: str = ""

    stub_mode: bool = True
    stub_latency_ms: int = 10000
    stub_success_rate: float = 0.8

    admin_email: str = "admin@trimvo.com"
    admin_password: str = "admin123"

    cors_origins: str = "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173"

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
