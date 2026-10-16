from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.services.booking import BookingService


def get_now() -> datetime:
    """The clock is a dependency so tests can freeze time (no sleeping, no flaky 'now')."""
    return datetime.now(UTC)


def get_service(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> BookingService:
    return BookingService(db, settings)


Now = Annotated[datetime, Depends(get_now)]
Service = Annotated[BookingService, Depends(get_service)]
