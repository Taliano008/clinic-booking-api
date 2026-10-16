"""Day-1 tests: prove the DATABASE enforces the booking invariants,
independent of any API code written later."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Appointment, AppointmentStatus

START = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)  # 09:00 Nairobi
END = START + timedelta(minutes=30)


def make(doctor, patient, **kw) -> Appointment:
    base = dict(doctor_id=doctor.id, patient_id=patient.id, start_time=START, end_time=END)
    return Appointment(**{**base, **kw})


def test_double_booking_same_slot_is_rejected(session, doctor, patient):
    session.add(make(doctor, patient))
    session.commit()
    session.add(make(doctor, patient))
    with pytest.raises(IntegrityError):
        session.commit()


def test_cancelled_slot_can_be_booked_again(session, doctor, patient):
    first = make(doctor, patient)
    session.add(first)
    session.commit()
    first.status = AppointmentStatus.CANCELLED
    first.cancel_reason = "Patient unwell"
    session.commit()

    session.add(make(doctor, patient))  # same doctor + start: must now succeed
    session.commit()
    assert session.query(Appointment).count() == 2  # history preserved


def test_same_time_different_doctor_is_allowed(session, doctor, patient):
    from app.models import Doctor

    other = Doctor(name="Dr. Other")
    session.add(other)
    session.commit()
    session.add_all([make(doctor, patient), make(other, patient)])
    session.commit()


def test_cancellation_requires_reason(session, doctor, patient):
    session.add(make(doctor, patient, status="cancelled", cancel_reason=None))
    with pytest.raises(IntegrityError):
        session.commit()


def test_invalid_status_rejected(session, doctor, patient):
    session.add(make(doctor, patient, status="maybe"))
    with pytest.raises(IntegrityError):
        session.commit()


def test_end_must_be_after_start(session, doctor, patient):
    session.add(make(doctor, patient, end_time=START - timedelta(minutes=30)))
    with pytest.raises(IntegrityError):
        session.commit()
