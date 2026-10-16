from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from app.deps import Now, Service
from app.schemas import AvailabilityOut, DoctorOut, SlotOut

router = APIRouter(prefix="/doctors", tags=["doctors"])


@router.get("", response_model=list[DoctorOut])
def list_doctors(service: Service) -> object:
    """List active doctors (handy for discovering ids)."""
    return service.list_doctors()


@router.get(
    "/{doctor_id}/availability",
    response_model=AvailabilityOut,
    responses={404: {"description": "Doctor not found"}},
)
def doctor_availability(
    doctor_id: int,
    day: Annotated[
        date,
        Query(alias="date", description="Clinic-local date, YYYY-MM-DD", examples=["2030-01-08"]),
    ],
    service: Service,
    now: Now,
) -> AvailabilityOut:
    """All bookable 30-minute slots for a doctor on a date (clinic-local).

    Already-booked slots and slots that are in the past or inside the minimum lead time
    are excluded, so every slot returned is one `POST /appointments` will accept.
    A day the doctor does not work returns an empty list."""
    slots = service.availability(doctor_id, day, now)
    return AvailabilityOut(
        doctor_id=doctor_id,
        date=day,
        timezone=service.tz_name,
        slot_minutes=service.slot_minutes,
        slots=[SlotOut(start_time=s.start, end_time=s.end) for s in slots],
    )
