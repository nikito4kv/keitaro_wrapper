"""Настройки приложения. Читаются из переменных окружения и файла .env."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Адрес трекера. Можно с хвостом /admin_api/v1, он будет отброшен.
    keitaro_url: str = ""
    keitaro_api_key: str = ""
    keitaro_timeout: float = 15.0

    database_url: str = "sqlite:///./keitaro_manager.db"

    # Куда первый поток отправляет посетителей из выбранных стран.
    geo_redirect_url: str = "https://google.com"


@lru_cache
def get_settings() -> Settings:
    return Settings()
