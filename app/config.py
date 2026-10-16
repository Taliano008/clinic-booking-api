from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All tunables live here so business rules are never magic numbers in code."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://clinic:clinic@localhost:5432/clinic"
    clinic_timezone: str = "Africa/Nairobi"  # working hours are expressed in this zone
    slot_minutes: int = 30
    min_lead_minutes: int = 60  # bonus rule: no bookings closer than this to "now"


@lru_cache
def get_settings() -> Settings:
    return Settings()
