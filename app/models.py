"""Database models.

Design notes (full reasoning is in README.md):
* All instants are stored as timezone-aware UTC. Working hours are wall-clock times in the
  clinic's timezone, because "9am" means 9am in Nairobi regardless of server locale.
* Slots are NOT stored. They are derived from WorkingHours minus active Appointments.
* The no-double-booking guarantee is enforced by a PARTIAL UNIQUE INDEX, not application code.
"""

import enum
from datetime import UTC, datetime, time
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    MetaData,
    String,
    Text,
    Time,
    TypeDecorator,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Deterministic constraint names => clean, reviewable Alembic migrations.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class UtcDateTime(TypeDecorator[datetime]):
    """timestamptz that ALWAYS round-trips as an aware UTC datetime.

    * refuses naive datetimes on the way in (no silent "which timezone?" bugs)
    * SQLite drops tzinfo; this puts it back, so tests on SQLite behave like PostgreSQL
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Naive datetime not allowed; use a timezone-aware datetime")
        return value.astimezone(UTC)

    def process_result_value(self, value: Any, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        result: datetime = value
        if result.tzinfo is None:
            return result.replace(tzinfo=UTC)
        return result.astimezone(UTC)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class AppointmentStatus(enum.StrEnum):
    BOOKED = "booked"
    CANCELLED = "cancelled"


class Doctor(Base):
    __tablename__ = "doctors"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    specialty: Mapped[str | None] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(default=True, server_default=text("true"))

    working_hours: Mapped[list["WorkingHours"]] = relationship(
        back_populates="doctor", cascade="all, delete-orphan"
    )
    appointments: Mapped[list["Appointment"]] = relationship(back_populates="doctor")


class WorkingHours(Base):
    """One block of working time for one doctor on one weekday (0=Mon .. 6=Sun).

    Multiple blocks per weekday are allowed so a lunch break is just two rows
    (08:00-12:00, 13:00-17:00). Times are clinic-local wall-clock.
    """

    __tablename__ = "working_hours"
    __table_args__ = (
        CheckConstraint("weekday BETWEEN 0 AND 6", name="weekday_range"),
        CheckConstraint("end_time > start_time", name="end_after_start"),
        UniqueConstraint("doctor_id", "weekday", "start_time"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id", ondelete="CASCADE"))
    weekday: Mapped[int]
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)

    doctor: Mapped[Doctor] = relationship(back_populates="working_hours")


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    phone: Mapped[str | None] = mapped_column(String(32))

    appointments: Mapped[list["Appointment"]] = relationship(back_populates="patient")


class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (
        CheckConstraint("status IN ('booked', 'cancelled')", name="status_valid"),
        CheckConstraint("end_time > start_time", name="end_after_start"),
        # A cancellation must always carry a reason (spec: "cancel with a reason").
        CheckConstraint(
            "status <> 'cancelled' OR cancel_reason IS NOT NULL", name="cancel_has_reason"
        ),
        # THE core invariant: at most one *active* appointment per doctor per start time.
        # Cancelled rows are exempt, so a cancelled slot is instantly bookable again
        # while the history row is kept for audit. Works on PostgreSQL and SQLite.
        Index(
            "uq_appointments_active_slot",
            "doctor_id",
            "start_time",
            unique=True,
            postgresql_where=text("status = 'booked'"),
            sqlite_where=text("status = 'booked'"),
        ),
        # Supports GET /patients/{id}/appointments (upcoming, sorted by date).
        Index("ix_appointments_patient_start", "patient_id", "start_time"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"))
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"))
    start_time: Mapped[datetime] = mapped_column(UtcDateTime())  # UTC
    end_time: Mapped[datetime] = mapped_column(UtcDateTime())  # UTC
    status: Mapped[str] = mapped_column(
        String(16), default=AppointmentStatus.BOOKED.value, server_default="booked"
    )
    cancel_reason: Mapped[str | None] = mapped_column(Text)
    cancelled_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime(), server_default=func.now(), onupdate=func.now()
    )

    doctor: Mapped[Doctor] = relationship(back_populates="appointments")
    patient: Mapped[Patient] = relationship(back_populates="appointments")
