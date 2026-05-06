from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Pulse Tickets API"
    api_v1_prefix: str = "/v1"
    database_url: str = "postgresql+psycopg://pulse:pulse@postgres:5432/pulse_tickets"
    auth_employee_token: str = "employee-token"
    auth_manager_token: str = "manager-token"
    seed_demo_data: bool = True
    jwt_secret_key: str = "change-me-for-local-dev"
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 60
    yandex_folder_id: str | None = None
    yandex_auth_token: str | None = None
    yandex_gpt_model: str = "yandexgpt-lite"
    yandex_gpt_temperature: float = 0.3
    yandex_gpt_max_tokens: int = 2000


@lru_cache
def get_settings() -> Settings:
    return Settings()
