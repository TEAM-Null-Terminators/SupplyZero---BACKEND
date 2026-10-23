from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./supplyzero.db"
    redis_url: str = "redis://localhost:6379/0"
    mqtt_host: str = "localhost"
    mqtt_port: int = 1883
    mqtt_username: str | None = None
    mqtt_password: str | None = None
    mqtt_enabled: bool = False
    osrm_base_url: str = "https://router.project-osrm.org"
    osrm_timeout_seconds: float = 1.2
    telemetry_gap_seconds: int = 300
    gap_degradation_factor: float = 3.0
    safety_margin_hours: float = 2.0
    auto_execute: bool = False
    route_cache_ttl_seconds: int = 60


@lru_cache
def get_settings() -> Settings:
    return Settings()
