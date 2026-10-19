from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import create_access_token
from app.config import Settings, get_settings
from app.database import get_db
from app.deps import CurrentPatient
from app.errors import NotFoundError
from app.models import Patient
from app.schemas import LoginRequest, PatientOut, TokenOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/token",
    response_model=TokenOut,
    summary="Authenticate patient and issue JWT bearer token",
    responses={404: {"description": "Patient not found"}},
)
def login(
    body: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenOut:
    """Issue a JWT token for a registered patient using their email."""
    patient = db.scalar(select(Patient).where(Patient.email == body.email))
    if not patient:
        raise NotFoundError("PATIENT_NOT_FOUND", f"Patient with email '{body.email}' not found")

    token = create_access_token(patient.id, patient.email, settings)
    return TokenOut(
        access_token=token,
        token_type="bearer",
        patient_id=patient.id,
        email=patient.email,
    )


@router.get(
    "/me",
    response_model=PatientOut,
    summary="Get profile of the authenticated patient",
    responses={401: {"description": "Missing or invalid token"}},
)
def get_me(current_patient: CurrentPatient) -> Patient:
    return current_patient
