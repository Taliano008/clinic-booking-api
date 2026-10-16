from typing import Any

from fastapi import APIRouter

from app.deps import Now, Service
from app.schemas import AppointmentCancel, AppointmentCreate, AppointmentOut, AppointmentReschedule

router = APIRouter(prefix="/appointments", tags=["appointments"])

_ERRORS: dict[int | str, dict[str, Any]] = {
    404: {"description": "Doctor, patient or appointment not found"},
    409: {"description": "Slot already taken / appointment already cancelled"},
    422: {"description": "Validation failed (past, outside working hours, misaligned, ...)"},
}


@router.post("", response_model=AppointmentOut, status_code=201, responses=_ERRORS)
def book_appointment(body: AppointmentCreate, service: Service, now: Now) -> object:
    """Book a slot. Must be on the slot grid, inside the doctor's working hours, in the
    future (with the configured minimum lead time) and not already taken."""
    return service.book(body.doctor_id, body.patient_id, body.start_time, now)


@router.get(
    "/{appointment_id}",
    response_model=AppointmentOut,
    responses={404: {"description": "Appointment not found"}},
)
def get_appointment(appointment_id: int, service: Service) -> object:
    return service.get_appointment(appointment_id)


@router.patch("/{appointment_id}/cancel", response_model=AppointmentOut, responses=_ERRORS)
def cancel_appointment(
    appointment_id: int, body: AppointmentCancel, service: Service, now: Now
) -> object:
    """Cancel with a reason. The slot becomes bookable again. 409 if already cancelled."""
    return service.cancel(appointment_id, body.reason, now)


@router.patch("/{appointment_id}/reschedule", response_model=AppointmentOut, responses=_ERRORS)
def reschedule_appointment(
    appointment_id: int, body: AppointmentReschedule, service: Service, now: Now
) -> object:
    """Move to a new slot with the same doctor. The new slot is validated exactly like a
    fresh booking; the old slot is freed atomically. 409 if the appointment is cancelled."""
    return service.reschedule(appointment_id, body.new_start_time, now)
