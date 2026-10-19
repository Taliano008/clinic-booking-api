from typing import Any

from fastapi import APIRouter

from app.deps import CurrentPatient, Now, Service
from app.errors import ForbiddenError
from app.schemas import AppointmentCancel, AppointmentCreate, AppointmentOut, AppointmentReschedule

router = APIRouter(prefix="/appointments", tags=["appointments"])

_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"description": "Authentication required"},
    403: {"description": "Action forbidden for the authenticated patient"},
    404: {"description": "Doctor, patient or appointment not found"},
    409: {"description": "Slot already taken / appointment already cancelled"},
    422: {"description": "Validation failed (past, outside working hours, misaligned, ...)"},
}


@router.post("", response_model=AppointmentOut, status_code=201, responses=_ERRORS)
def book_appointment(
    body: AppointmentCreate, current_patient: CurrentPatient, service: Service, now: Now
) -> object:
    """Book a slot. The authenticated patient can only book for themselves."""
    if body.patient_id is not None and body.patient_id != current_patient.id:
        raise ForbiddenError("FORBIDDEN", "Cannot book appointments for other patients")
    return service.book(body.doctor_id, current_patient.id, body.start_time, now)


@router.get(
    "/{appointment_id}",
    response_model=AppointmentOut,
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Access denied to other patient's appointment"},
        404: {"description": "Appointment not found"},
    },
)
def get_appointment(
    appointment_id: int, current_patient: CurrentPatient, service: Service
) -> object:
    """Get appointment details. Only the patient who owns the appointment can view it."""
    appt = service.get_appointment(appointment_id)
    if appt.patient_id != current_patient.id:
        raise ForbiddenError("FORBIDDEN", "Access denied: you can only view your own appointments")
    return appt


@router.patch("/{appointment_id}/cancel", response_model=AppointmentOut, responses=_ERRORS)
def cancel_appointment(
    appointment_id: int,
    body: AppointmentCancel,
    current_patient: CurrentPatient,
    service: Service,
    now: Now,
) -> object:
    """Cancel with a reason. Only the patient who owns the appointment can cancel it."""
    appt = service.get_appointment(appointment_id)
    if appt.patient_id != current_patient.id:
        raise ForbiddenError(
            "FORBIDDEN", "Access denied: you can only cancel your own appointments"
        )
    return service.cancel(appointment_id, body.reason, now)


@router.patch("/{appointment_id}/reschedule", response_model=AppointmentOut, responses=_ERRORS)
def reschedule_appointment(
    appointment_id: int,
    body: AppointmentReschedule,
    current_patient: CurrentPatient,
    service: Service,
    now: Now,
) -> object:
    """Reschedule an appointment. Only the patient who owns the appointment can reschedule it."""
    appt = service.get_appointment(appointment_id)
    if appt.patient_id != current_patient.id:
        raise ForbiddenError(
            "FORBIDDEN", "Access denied: you can only reschedule your own appointments"
        )
    return service.reschedule(appointment_id, body.new_start_time, now)
