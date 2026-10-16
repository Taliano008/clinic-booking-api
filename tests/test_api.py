from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from app.deps import get_now
from app.main import app

EAT = ZoneInfo("Africa/Nairobi")  # UTC+3


def test_list_doctors(client: TestClient, doctor_with_schedule):
    res = client.get("/doctors")
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 1
    assert data[0]["id"] == doctor_with_schedule.id
    assert data[0]["name"] == doctor_with_schedule.name


def test_doctor_availability(client: TestClient, doctor_with_schedule):
    # Fixed fake 'now': Monday 2030-01-07 05:00 UTC (08:00 EAT)
    fake_now = datetime(2030, 1, 7, 5, 0, tzinfo=UTC)
    app.dependency_overrides[get_now] = lambda: fake_now

    # Tuesday 2030-01-08: doctor works 08:00-12:00 and 13:00-17:00 EAT
    res = client.get(f"/doctors/{doctor_with_schedule.id}/availability?date=2030-01-08")
    assert res.status_code == 200
    data = res.json()
    assert data["doctor_id"] == doctor_with_schedule.id
    assert data["date"] == "2030-01-08"
    assert data["timezone"] == "Africa/Nairobi"
    assert data["slot_minutes"] == 30
    # 08:00-12:00 = 8 slots, 13:00-17:00 = 8 slots -> 16 slots total
    assert len(data["slots"]) == 16
    assert data["slots"][0]["start_time"] == "2030-01-08T08:00:00+03:00"
    assert data["slots"][-1]["start_time"] == "2030-01-08T16:30:00+03:00"


def test_doctor_availability_weekend_empty(client: TestClient, doctor_with_schedule):
    fake_now = datetime(2030, 1, 7, 5, 0, tzinfo=UTC)
    app.dependency_overrides[get_now] = lambda: fake_now

    # Saturday 2030-01-12: doctor doesn't work weekends
    res = client.get(f"/doctors/{doctor_with_schedule.id}/availability?date=2030-01-12")
    assert res.status_code == 200
    assert res.json()["slots"] == []


def test_doctor_availability_not_found(client: TestClient):
    res = client.get("/doctors/99999/availability?date=2030-01-08")
    assert res.status_code == 404
    assert res.json()["code"] == "DOCTOR_NOT_FOUND"


def test_book_appointment_success(client: TestClient, doctor_with_schedule, patient):
    fake_now = datetime(2030, 1, 7, 5, 0, tzinfo=UTC)
    app.dependency_overrides[get_now] = lambda: fake_now

    payload = {
        "doctor_id": doctor_with_schedule.id,
        "patient_id": patient.id,
        "start_time": "2030-01-08T09:00:00+03:00",
    }
    res = client.post("/appointments", json=payload)
    assert res.status_code == 201
    body = res.json()
    assert body["doctor_id"] == doctor_with_schedule.id
    assert body["patient_id"] == patient.id
    assert body["start_time"] == "2030-01-08T09:00:00+03:00"
    assert body["end_time"] == "2030-01-08T09:30:00+03:00"
    assert body["status"] == "booked"


def test_book_appointment_double_booking_conflict(
    client: TestClient, doctor_with_schedule, patient
):
    fake_now = datetime(2030, 1, 7, 5, 0, tzinfo=UTC)
    app.dependency_overrides[get_now] = lambda: fake_now

    payload = {
        "doctor_id": doctor_with_schedule.id,
        "patient_id": patient.id,
        "start_time": "2030-01-08T09:00:00+03:00",
    }
    r1 = client.post("/appointments", json=payload)
    assert r1.status_code == 201

    # Second booking for the exact same slot -> 409 Conflict
    r2 = client.post("/appointments", json=payload)
    assert r2.status_code == 409
    assert r2.json()["code"] == "SLOT_TAKEN"


def test_book_appointment_misaligned_boundary(client: TestClient, doctor_with_schedule, patient):
    fake_now = datetime(2030, 1, 7, 5, 0, tzinfo=UTC)
    app.dependency_overrides[get_now] = lambda: fake_now

    payload = {
        "doctor_id": doctor_with_schedule.id,
        "patient_id": patient.id,
        "start_time": "2030-01-08T09:15:00+03:00",  # not on :00 or :30
    }
    res = client.post("/appointments", json=payload)
    assert res.status_code == 422
    assert res.json()["code"] == "MISALIGNED_SLOT"


def test_book_appointment_outside_working_hours(client: TestClient, doctor_with_schedule, patient):
    fake_now = datetime(2030, 1, 7, 5, 0, tzinfo=UTC)
    app.dependency_overrides[get_now] = lambda: fake_now

    payload = {
        "doctor_id": doctor_with_schedule.id,
        "patient_id": patient.id,
        "start_time": "2030-01-08T12:00:00+03:00",  # Lunch break 12:00-13:00
    }
    res = client.post("/appointments", json=payload)
    assert res.status_code == 422
    assert res.json()["code"] == "OUTSIDE_WORKING_HOURS"


def test_book_appointment_slot_in_past(client: TestClient, doctor_with_schedule, patient):
    fake_now = datetime(2030, 1, 8, 10, 0, tzinfo=UTC)  # 13:00 EAT
    app.dependency_overrides[get_now] = lambda: fake_now

    payload = {
        "doctor_id": doctor_with_schedule.id,
        "patient_id": patient.id,
        "start_time": "2030-01-08T09:00:00+03:00",  # In the past
    }
    res = client.post("/appointments", json=payload)
    assert res.status_code == 422
    assert res.json()["code"] == "SLOT_IN_PAST"


def test_book_appointment_slot_too_soon(client: TestClient, doctor_with_schedule, patient):
    fake_now = datetime(2030, 1, 8, 5, 45, tzinfo=UTC)  # 08:45 EAT
    app.dependency_overrides[get_now] = lambda: fake_now

    payload = {
        "doctor_id": doctor_with_schedule.id,
        "patient_id": patient.id,
        "start_time": "2030-01-08T09:00:00+03:00",  # Only 15 mins away (< min 60 mins lead)
    }
    res = client.post("/appointments", json=payload)
    assert res.status_code == 422
    assert res.json()["code"] == "SLOT_TOO_SOON"


def test_cancel_appointment_and_rebook(client: TestClient, doctor_with_schedule, patient):
    fake_now = datetime(2030, 1, 7, 5, 0, tzinfo=UTC)
    app.dependency_overrides[get_now] = lambda: fake_now

    # Book slot
    payload = {
        "doctor_id": doctor_with_schedule.id,
        "patient_id": patient.id,
        "start_time": "2030-01-08T10:00:00+03:00",
    }
    r_book = client.post("/appointments", json=payload)
    assert r_book.status_code == 201
    appt_id = r_book.json()["id"]

    # Cancel slot
    r_cancel = client.patch(f"/appointments/{appt_id}/cancel", json={"reason": "Schedule conflict"})
    assert r_cancel.status_code == 200
    assert r_cancel.json()["status"] == "cancelled"
    assert r_cancel.json()["cancel_reason"] == "Schedule conflict"

    # Cancelling again -> 409 Conflict
    r_cancel_again = client.patch(
        f"/appointments/{appt_id}/cancel", json={"reason": "Another reason"}
    )
    assert r_cancel_again.status_code == 409
    assert r_cancel_again.json()["code"] == "ALREADY_CANCELLED"

    # The cancelled slot can now be booked again!
    r_rebook = client.post("/appointments", json=payload)
    assert r_rebook.status_code == 201


def test_reschedule_appointment(client: TestClient, doctor_with_schedule, patient):
    fake_now = datetime(2030, 1, 7, 5, 0, tzinfo=UTC)
    app.dependency_overrides[get_now] = lambda: fake_now

    # Book initial slot at 10:00
    r_book = client.post(
        "/appointments",
        json={
            "doctor_id": doctor_with_schedule.id,
            "patient_id": patient.id,
            "start_time": "2030-01-08T10:00:00+03:00",
        },
    )
    appt_id = r_book.json()["id"]

    # Reschedule to same slot -> 422 SAME_SLOT
    r_same = client.patch(
        f"/appointments/{appt_id}/reschedule",
        json={"new_start_time": "2030-01-08T10:00:00+03:00"},
    )
    assert r_same.status_code == 422
    assert r_same.json()["code"] == "SAME_SLOT"

    # Reschedule to 14:00
    r_resched = client.patch(
        f"/appointments/{appt_id}/reschedule",
        json={"new_start_time": "2030-01-08T14:00:00+03:00"},
    )
    assert r_resched.status_code == 200
    assert r_resched.json()["start_time"] == "2030-01-08T14:00:00+03:00"

    # The old slot (10:00) is now free for another booking
    r_old_slot = client.post(
        "/appointments",
        json={
            "doctor_id": doctor_with_schedule.id,
            "patient_id": patient.id,
            "start_time": "2030-01-08T10:00:00+03:00",
        },
    )
    assert r_old_slot.status_code == 201


def test_patient_upcoming_appointments(client: TestClient, doctor_with_schedule, patient):
    fake_now = datetime(2030, 1, 7, 5, 0, tzinfo=UTC)
    app.dependency_overrides[get_now] = lambda: fake_now

    # Book 2 appointments
    client.post(
        "/appointments",
        json={
            "doctor_id": doctor_with_schedule.id,
            "patient_id": patient.id,
            "start_time": "2030-01-08T11:00:00+03:00",
        },
    )
    client.post(
        "/appointments",
        json={
            "doctor_id": doctor_with_schedule.id,
            "patient_id": patient.id,
            "start_time": "2030-01-08T10:00:00+03:00",
        },
    )

    res = client.get(f"/patients/{patient.id}/appointments")
    assert res.status_code == 200
    appts = res.json()
    assert len(appts) == 2
    # Verify sorted soonest first
    assert appts[0]["start_time"] == "2030-01-08T10:00:00+03:00"
    assert appts[1]["start_time"] == "2030-01-08T11:00:00+03:00"
