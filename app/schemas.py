from datetime import date, datetime
from typing import Annotated

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    PlainSerializer,
    StringConstraints,
)

from app.models import AppointmentStatus
from app.timeutils import clinic_tz


def _to_clinic_iso(dt: datetime) -> str:
    return dt.astimezone(clinic_tz()).isoformat()


# Stored in UTC, *presented* in clinic-local time with an explicit offset (e.g. +03:00):
# unambiguous for machines, readable for patients.
ClinicDatetime = Annotated[
    datetime, PlainSerializer(_to_clinic_iso, return_type=str, when_used="always")
]


# ---------- requests ----------
class AppointmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doctor_id: int = Field(gt=0, examples=[1])
    patient_id: int = Field(gt=0, examples=[1])
    start_time: AwareDatetime = Field(
        description="Slot start, ISO-8601 WITH a UTC offset (naive times are rejected).",
        examples=["2030-01-08T10:00:00+03:00"],
    )


class AppointmentCancel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
    ] = Field(examples=["Feeling better, no longer need the visit"])


class AppointmentReschedule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    new_start_time: AwareDatetime = Field(examples=["2030-01-08T14:30:00+03:00"])


# ---------- responses ----------
class AppointmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    doctor_id: int
    patient_id: int
    start_time: ClinicDatetime
    end_time: ClinicDatetime
    status: AppointmentStatus
    cancel_reason: str | None
    cancelled_at: ClinicDatetime | None
    created_at: ClinicDatetime
    updated_at: ClinicDatetime


class SlotOut(BaseModel):
    start_time: ClinicDatetime
    end_time: ClinicDatetime


class AvailabilityOut(BaseModel):
    doctor_id: int
    date: date
    timezone: str
    slot_minutes: int
    slots: list[SlotOut]


class DoctorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    specialty: str | None
