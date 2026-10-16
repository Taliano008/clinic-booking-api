from functools import lru_cache
from zoneinfo import ZoneInfo

from app.config import get_settings


@lru_cache
def get_zone(name: str) -> ZoneInfo:
    return ZoneInfo(name)


def clinic_tz() -> ZoneInfo:
    return get_zone(get_settings().clinic_timezone)
