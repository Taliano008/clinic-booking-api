from fastapi import APIRouter

from app.deps import CurrentPatient, Now, Service
from app.errors import ForbiddenError
from app.schemas import AppointmentOut

router = APIRouter(prefix="/patients", tags=["patients"])


@router.get(
    "/me/appointments",
    response_model=list[AppointmentOut],
    responses={401: {"description": "Authentication required"}},
)
def my_upcoming_appointments(current_patient: CurrentPatient, service: Service, now: Now) -> object:
    """Upcoming (not cancelled, not yet started) appointments for the authenticated patient."""
    return service.upcoming_for_patient(current_patient.id, now)


@router.get(
    "/{patient_id}/appointments",
    response_model=list[AppointmentOut],
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Access denied to other patient's appointments"},
        404: {"description": "Patient not found"},
    },
)
def upcoming_appointments(
    patient_id: int, current_patient: CurrentPatient, service: Service, now: Now
) -> object:
    """Upcoming (not cancelled, not yet started) appointments, soonest first.
    Patients can only view their own appointments."""
    if patient_id != current_patient.id:
        raise ForbiddenError("FORBIDDEN", "Access denied: you can only view your own appointments")
    return service.upcoming_for_patient(patient_id, now)
