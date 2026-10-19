from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth import decode_access_token
from app.config import Settings, get_settings
from app.database import get_db
from app.errors import UnauthorizedError
from app.models import Patient
from app.services.booking import BookingService

_bearer_security = HTTPBearer(auto_error=False)


def get_now() -> datetime:
    """The clock is a dependency so tests can freeze time (no sleeping, no flaky 'now')."""
    return datetime.now(UTC)


def get_service(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> BookingService:
    return BookingService(db, settings)


def get_current_patient(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_security)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Patient:
    if not credentials or not credentials.credentials:
        raise UnauthorizedError("UNAUTHORIZED", "Missing Bearer authentication token")

    payload = decode_access_token(credentials.credentials, settings)
    sub = payload.get("sub")
    if not sub:
        raise UnauthorizedError("INVALID_TOKEN", "Token payload missing subject")

    try:
        patient_id = int(sub)
    except (ValueError, TypeError) as exc:
        raise UnauthorizedError("INVALID_TOKEN", "Malformed subject in token") from exc

    patient = db.get(Patient, patient_id)
    if not patient:
        raise UnauthorizedError("PATIENT_NOT_FOUND", "Authenticated patient no longer exists")

    return patient


Now = Annotated[datetime, Depends(get_now)]
Service = Annotated[BookingService, Depends(get_service)]
CurrentPatient = Annotated[Patient, Depends(get_current_patient)]
