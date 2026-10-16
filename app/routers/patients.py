from fastapi import APIRouter

from app.deps import Now, Service
from app.schemas import AppointmentOut

router = APIRouter(prefix="/patients", tags=["patients"])


@router.get(
    "/{patient_id}/appointments",
    response_model=list[AppointmentOut],
    responses={404: {"description": "Patient not found"}},
)
def upcoming_appointments(patient_id: int, service: Service, now: Now) -> object:
    """Upcoming (not cancelled, not yet started) appointments, soonest first."""
    return service.upcoming_for_patient(patient_id, now)
