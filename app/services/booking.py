"""Booking rules. Every write path (book, reschedule) goes through `_validate_slot`, so a
rescheduled slot is validated EXACTLY like a fresh booking - by construction, not by copy-paste.

The database (partial unique index) is the final arbiter for double-booking; the explicit
`_slot_taken` pre-check just gives a clean 409 on the common path without an exception.
"""

from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings
from app.errors import ConflictError, NotFoundError, UnprocessableError
from app.models import Appointment, AppointmentStatus, Doctor, Patient, WorkingHours
from app.services.slots import Slot, bookable, generate_slots
from app.timeutils import get_zone

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


class BookingService:
    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.slot_minutes = settings.slot_minutes
        self.min_lead = timedelta(minutes=settings.min_lead_minutes)
        self.tz_name = settings.clinic_timezone
        self.tz = get_zone(settings.clinic_timezone)

    # ------------------------------------------------------------------ lookups
    def list_doctors(self) -> list[Doctor]:
        return list(self.db.scalars(select(Doctor).where(Doctor.is_active).order_by(Doctor.id)))

    def get_doctor(self, doctor_id: int) -> Doctor:
        doctor = self.db.get(Doctor, doctor_id)
        if doctor is None or not doctor.is_active:
            raise NotFoundError("DOCTOR_NOT_FOUND", f"Doctor {doctor_id} not found")
        return doctor

    def get_patient(self, patient_id: int) -> Patient:
        patient = self.db.get(Patient, patient_id)
        if patient is None:
            raise NotFoundError("PATIENT_NOT_FOUND", f"Patient {patient_id} not found")
        return patient

    def get_appointment(self, appointment_id: int, *, lock: bool = False) -> Appointment:
        stmt = select(Appointment).where(Appointment.id == appointment_id)
        if lock:  # SELECT ... FOR UPDATE on PostgreSQL (no-op on SQLite); serialises writers
            stmt = stmt.with_for_update()
        appt = self.db.scalar(stmt)
        if appt is None:
            raise NotFoundError("APPOINTMENT_NOT_FOUND", f"Appointment {appointment_id} not found")
        return appt

    def _blocks(self, doctor_id: int, weekday: int) -> list[tuple[time, time]]:
        rows = self.db.execute(
            select(WorkingHours.start_time, WorkingHours.end_time)
            .where(WorkingHours.doctor_id == doctor_id, WorkingHours.weekday == weekday)
            .order_by(WorkingHours.start_time)
        )
        return [(r.start_time, r.end_time) for r in rows]

    def _slot_taken(self, doctor_id: int, start: datetime) -> bool:
        return (
            self.db.scalar(
                select(Appointment.id).where(
                    Appointment.doctor_id == doctor_id,
                    Appointment.start_time == start,
                    Appointment.status == AppointmentStatus.BOOKED.value,
                )
            )
            is not None
        )

    # ---------------------------------------------------------------- validation
    def _validate_slot(self, doctor: Doctor, start: datetime, now: datetime) -> datetime:
        """Return the normalised (UTC) start if bookable, else raise a precise error."""
        start = start.astimezone(UTC)
        local = start.astimezone(self.tz)

        if local.second or local.microsecond or local.minute % self.slot_minutes:
            raise UnprocessableError(
                "MISALIGNED_SLOT",
                f"Start time must fall on a {self.slot_minutes}-minute boundary "
                f"(e.g. 09:00, 09:30); got {local:%H:%M:%S}",
            )
        if start <= now:
            raise UnprocessableError("SLOT_IN_PAST", "Cannot book a slot in the past")
        if start < now + self.min_lead:
            mins = int(self.min_lead.total_seconds() // 60)
            raise UnprocessableError(
                "SLOT_TOO_SOON", f"Appointments must be booked at least {mins} minutes in advance"
            )

        blocks = self._blocks(doctor.id, local.weekday())
        day_name = WEEKDAYS[local.weekday()]
        if not blocks:
            raise UnprocessableError(
                "DOCTOR_NOT_WORKING", f"{doctor.name} does not work on {day_name}s"
            )
        valid = {s.start for s in generate_slots(blocks, local.date(), self.tz, self.slot_minutes)}
        if start not in valid:
            hours = ", ".join(f"{a:%H:%M}-{b:%H:%M}" for a, b in blocks)
            raise UnprocessableError(
                "OUTSIDE_WORKING_HOURS",
                f"{doctor.name} works {hours} on {day_name}s ({self.tz_name}); "
                "the whole slot must fall inside these hours",
            )
        return start

    # ------------------------------------------------------------------- queries
    def availability(self, doctor_id: int, day: date, now: datetime) -> list[Slot]:
        doctor = self.get_doctor(doctor_id)
        slots = generate_slots(
            self._blocks(doctor.id, day.weekday()), day, self.tz, self.slot_minutes
        )
        if not slots:
            return []
        taken = set(
            self.db.scalars(
                select(Appointment.start_time).where(
                    Appointment.doctor_id == doctor.id,
                    Appointment.status == AppointmentStatus.BOOKED.value,
                    Appointment.start_time >= slots[0].start,
                    Appointment.start_time <= slots[-1].start,
                )
            )
        )
        return bookable(slots, taken, now, self.min_lead)

    def upcoming_for_patient(self, patient_id: int, now: datetime) -> list[Appointment]:
        self.get_patient(patient_id)
        return list(
            self.db.scalars(
                select(Appointment)
                .where(
                    Appointment.patient_id == patient_id,
                    Appointment.status == AppointmentStatus.BOOKED.value,
                    Appointment.start_time >= now,
                )
                .order_by(Appointment.start_time, Appointment.id)
            )
        )

    # -------------------------------------------------------------------- writes
    def book(self, doctor_id: int, patient_id: int, start: datetime, now: datetime) -> Appointment:
        doctor = self.get_doctor(doctor_id)
        self.get_patient(patient_id)
        start = self._validate_slot(doctor, start, now)
        if self._slot_taken(doctor.id, start):
            raise self._slot_taken_error(doctor, start)

        appt = Appointment(
            doctor_id=doctor.id,
            patient_id=patient_id,
            start_time=start,
            end_time=start + timedelta(minutes=self.slot_minutes),
        )
        self.db.add(appt)
        self._commit_or_conflict(doctor, start)
        self.db.refresh(appt)
        return appt

    def cancel(self, appointment_id: int, reason: str, now: datetime) -> Appointment:
        appt = self.get_appointment(appointment_id, lock=True)
        if appt.status == AppointmentStatus.CANCELLED:
            raise ConflictError(
                "ALREADY_CANCELLED", f"Appointment {appointment_id} is already cancelled"
            )
        appt.status = AppointmentStatus.CANCELLED.value
        appt.cancel_reason = reason
        appt.cancelled_at = now
        self.db.commit()
        self.db.refresh(appt)
        return appt

    def reschedule(self, appointment_id: int, new_start: datetime, now: datetime) -> Appointment:
        appt = self.get_appointment(appointment_id, lock=True)
        if appt.status == AppointmentStatus.CANCELLED:
            raise ConflictError(
                "APPOINTMENT_CANCELLED",
                f"Appointment {appointment_id} is cancelled and cannot be rescheduled; "
                "book a new appointment instead",
            )
        doctor = self.get_doctor(appt.doctor_id)
        new_start = self._validate_slot(doctor, new_start, now)
        if new_start == appt.start_time:
            raise UnprocessableError(
                "SAME_SLOT", "The new time is the same as the current appointment time"
            )
        if self._slot_taken(doctor.id, new_start):
            raise self._slot_taken_error(doctor, new_start)

        # One UPDATE in one transaction: the old slot frees and the new one is claimed
        # atomically. If the new slot is lost to a race, the rollback leaves the patient's
        # ORIGINAL appointment untouched.
        appt.start_time = new_start
        appt.end_time = new_start + timedelta(minutes=self.slot_minutes)
        self._commit_or_conflict(doctor, new_start)
        self.db.refresh(appt)
        return appt

    # ------------------------------------------------------------------- helpers
    def _slot_taken_error(self, doctor: Doctor, start: datetime) -> ConflictError:
        local = start.astimezone(self.tz)
        return ConflictError(
            "SLOT_TAKEN", f"{doctor.name} is already booked at {local:%Y-%m-%d %H:%M}"
        )

    def _commit_or_conflict(self, doctor: Doctor, start: datetime) -> None:
        """Commit; if the unique index rejects us we lost a race -> clean 409, not a 500."""
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            if self._slot_taken(doctor.id, start):
                raise self._slot_taken_error(doctor, start) from None
            raise
