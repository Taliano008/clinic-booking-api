"""Comprehensive End-to-End Live Feature Test Script

Tests all API features across Doctors and Patients against the running backend:
1. Health check
2. Doctor listing and details
3. Doctor availability calculation (working day vs non-working day)
4. Patient authentication & JWT issuance (including invalid email handling)
5. Patient profile retrieval & 401 Unauthorized handling
6. Slot booking (POST /appointments)
7. Concurrency & double-booking prevention (409 Conflict)
8. Cross-patient booking protection (403 Forbidden)
9. Patient appointment listing (GET /patients/me/appointments)
10. Appointment detail retrieval & cross-patient privacy protection
11. Reschedule appointment to a new slot (PATCH /appointments/{id}/reschedule)
12. Verify slot transitions
13. Cancel appointment with mandatory reason (PATCH /appointments/{id}/cancel)
14. Double-cancellation protection (409 Conflict)
15. Direct database verification (inspects tables in the configured database)
"""

import os
import sys
from datetime import UTC, datetime, timedelta

# Ensure repo root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import httpx
from sqlalchemy import func, select

from app.config import get_settings
from app.database import SessionLocal
from app.models import Appointment, Doctor, Patient

BASE_URL = "http://127.0.0.1:8000"


def log(step: str, status: str, details: str = ""):
    icon = "PASSED" if status == "OK" else "FAILED"
    print(f"[{icon}] {step}")
    if details:
        for line in details.strip().splitlines():
            print(f"       {line}")


def run_tests():
    print("=" * 70)
    print("CLINIC BOOKING API - COMPREHENSIVE FEATURE TEST SUITE")
    print(f"Configured Database: {get_settings().database_url}")

    try:
        live_client = httpx.Client(base_url=BASE_URL, timeout=3.0)
        r = live_client.get("/health")
        if r.status_code == 200:
            client = live_client
            print(f"Target: Live Uvicorn Server ({BASE_URL})")
        else:
            raise Exception("Server returned non-200")
    except Exception:
        from fastapi.testclient import TestClient

        from app.main import app

        client = TestClient(app)
        print("Target: Direct FastAPI Application & Database (TestClient)")
    print("=" * 70)

    passed_count = 0
    total_count = 0

    def check(step_name: str, condition: bool, details: str = ""):
        nonlocal passed_count, total_count
        total_count += 1
        if condition:
            passed_count += 1
            log(step_name, "OK", details)
        else:
            log(step_name, "FAIL", details)
            print(f"\nFATAL: Check failed for {step_name}")
            sys.exit(1)

    # -------------------------------------------------------------------------
    # 1. Health check
    # -------------------------------------------------------------------------
    res = client.get("/health")
    check(
        "1. Health Check",
        res.status_code == 200 and res.json() == {"status": "ok"},
        f"Response: {res.json()}",
    )

    # -------------------------------------------------------------------------
    # 2. Doctors listing
    # -------------------------------------------------------------------------
    res = client.get("/doctors")
    doctors = res.json()
    check(
        "2. List Active Doctors",
        res.status_code == 200 and len(doctors) >= 5,
        f"Found {len(doctors)} doctors. First doctor: {doctors[0]['name'] if doctors else 'None'}",
    )
    doc_1 = doctors[0]["id"]
    doc_1_name = doctors[0]["name"]

    # -------------------------------------------------------------------------
    # 3. Doctor Availability Calculation
    # -------------------------------------------------------------------------
    # Find next Wednesday (future date)
    today = datetime.now(UTC).date()
    # pick a date 7 days in the future to ensure all working hours are unexpired
    future_date = today + timedelta(days=7)
    # Ensure it's a weekday (0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri)
    while future_date.weekday() not in (0, 1, 2, 3, 4):
        future_date += timedelta(days=1)

    date_str = future_date.isoformat()
    res = client.get(f"/doctors/{doc_1}/availability?date={date_str}")
    avail = res.json()
    check(
        f"3. Doctor Availability on Working Day ({date_str})",
        res.status_code == 200 and len(avail.get("slots", [])) > 0,
        f"Doctor '{doc_1_name}' has {len(avail.get('slots', []))} available 30-min slots.",
    )

    # Test non-working day (Sunday)
    sunday = today + timedelta(days=(6 - today.weekday() + 7) % 7 or 7)
    res_sun = client.get(f"/doctors/{doc_1}/availability?date={sunday.isoformat()}")
    check(
        f"4. Doctor Availability on Non-Working Day (Sunday {sunday.isoformat()})",
        res_sun.status_code == 200 and len(res_sun.json().get("slots", [])) == 0,
        f"Sunday correctly returns 0 slots: {res_sun.json().get('slots')}",
    )

    # -------------------------------------------------------------------------
    # 4. Patient Authentication & JWT issuance
    # -------------------------------------------------------------------------
    # Positive: Login as patient 1
    res_auth1 = client.post("/auth/token", json={"email": "patient1@example.com"})
    token_p1 = res_auth1.json().get("access_token")
    headers_p1 = {"Authorization": f"Bearer {token_p1}"}
    check(
        "5. Patient 1 Login & JWT Generation",
        res_auth1.status_code == 200 and bool(token_p1),
        f"Issued Bearer token for patient1@example.com (id: {res_auth1.json().get('patient_id')})",
    )

    # Positive: Login as patient 2
    res_auth2 = client.post("/auth/token", json={"email": "patient2@example.com"})
    token_p2 = res_auth2.json().get("access_token")
    headers_p2 = {"Authorization": f"Bearer {token_p2}"}
    check(
        "6. Patient 2 Login & JWT Generation",
        res_auth2.status_code == 200 and bool(token_p2),
        f"Issued Bearer token for patient2@example.com (id: {res_auth2.json().get('patient_id')})",
    )

    # Negative: Login with unknown email
    res_bad_auth = client.post("/auth/token", json={"email": "nonexistent@example.com"})
    check(
        "7. Authentication Rejection for Unknown Patient",
        res_bad_auth.status_code == 404 and res_bad_auth.json().get("code") == "PATIENT_NOT_FOUND",
        f"Status {res_bad_auth.status_code}, error code: {res_bad_auth.json().get('code')}",
    )

    # -------------------------------------------------------------------------
    # 5. Profile & Security Guard
    # -------------------------------------------------------------------------
    res_me = client.get("/auth/me", headers=headers_p1)
    me_data = res_me.json()
    check(
        "8. Get Authenticated Patient Profile (/auth/me)",
        res_me.status_code == 200 and me_data["email"] == "patient1@example.com",
        f"Profile: ID={me_data['id']}, Name={me_data['name']}, Email={me_data['email']}",
    )

    res_no_auth = client.get("/auth/me")
    check(
        "9. Access Denial Without Authentication Token (401)",
        res_no_auth.status_code == 401 and res_no_auth.json().get("code") == "UNAUTHORIZED",
        f"Correctly returned 401 Unauthorized: {res_no_auth.json().get('detail')}",
    )

    # -------------------------------------------------------------------------
    # 6. Book an Appointment
    # -------------------------------------------------------------------------
    free_slot = avail["slots"][0]
    slot_start = free_slot["start_time"]
    booking_payload = {
        "doctor_id": doc_1,
        "start_time": slot_start,
    }
    res_book = client.post("/appointments", json=booking_payload, headers=headers_p1)
    appt = res_book.json()
    check(
        f"10. Book Appointment for Doctor '{doc_1_name}' at {slot_start}",
        res_book.status_code == 201 and appt.get("status") == "booked",
        f"Appointment created with ID: {appt.get('id')}, Status: {appt.get('status')}",
    )
    appt_id = appt.get("id")

    # -------------------------------------------------------------------------
    # 7. Double-Booking Prevention (Concurrency & Uniqueness)
    # -------------------------------------------------------------------------
    res_dup = client.post("/appointments", json=booking_payload, headers=headers_p2)
    check(
        "11. Double-Booking Prevention (409 Conflict)",
        res_dup.status_code == 409 and res_dup.json().get("code") == "SLOT_TAKEN",
        f"Correctly rejected duplicate booking with 409 Conflict: {res_dup.json().get('detail')}",
    )

    p2_id = res_auth2.json()["patient_id"]

    # -------------------------------------------------------------------------
    # 8. Cross-Patient Booking Prevention
    # -------------------------------------------------------------------------
    # Patient 1 tries to specify Patient 2's ID in body
    res_spoof = client.post(
        "/appointments",
        json={
            "doctor_id": doc_1,
            "start_time": avail["slots"][1]["start_time"],
            "patient_id": p2_id,
        },
        headers=headers_p1,
    )
    check(
        "12. Cross-Patient Booking Impersonation Prevention (403)",
        res_spoof.status_code == 403 and res_spoof.json().get("code") == "FORBIDDEN",
        f"Correctly rejected with 403 Forbidden: {res_spoof.json().get('detail')}",
    )

    # -------------------------------------------------------------------------
    # 9. View Patient Appointments
    # -------------------------------------------------------------------------
    res_my_appts = client.get("/patients/me/appointments", headers=headers_p1)
    my_appts = res_my_appts.json()
    booked_ids = [a["id"] for a in my_appts]
    check(
        "13. Patient View Upcoming Appointments (/patients/me/appointments)",
        res_my_appts.status_code == 200 and appt_id in booked_ids,
        f"Found {len(my_appts)} upcoming appointment(s). Target appt #{appt_id} is present.",
    )

    # Cross-patient privacy check
    res_other_appts = client.get(
        f"/patients/{res_me.json()['id']}/appointments", headers=headers_p2
    )
    check(
        "14. Cross-Patient Appointment List Privacy Protection (403)",
        res_other_appts.status_code == 403,
        "Patient 2 denied access to Patient 1's appointments list.",
    )

    # -------------------------------------------------------------------------
    # 10. View Appointment Details
    # -------------------------------------------------------------------------
    res_single = client.get(f"/appointments/{appt_id}", headers=headers_p1)
    s_data = res_single.json()
    check(
        f"15. Get Appointment Details (/appointments/{appt_id})",
        res_single.status_code == 200 and s_data["id"] == appt_id,
        f"Details: Doctor ID={s_data['doctor_id']}, Start={s_data['start_time']}",
    )

    res_single_forbidden = client.get(f"/appointments/{appt_id}", headers=headers_p2)
    check(
        "16. Unauthorized Patient Cannot View Details of Other's Appointment (403)",
        res_single_forbidden.status_code == 403,
        f"Patient 2 correctly forbidden from reading Appointment #{appt_id}",
    )

    # -------------------------------------------------------------------------
    # 11. Reschedule Appointment
    # -------------------------------------------------------------------------
    new_slot = avail["slots"][2]["start_time"]
    res_resched = client.patch(
        f"/appointments/{appt_id}/reschedule",
        json={"new_start_time": new_slot},
        headers=headers_p1,
    )
    check(
        f"17. Reschedule Appointment #{appt_id} to {new_slot}",
        res_resched.status_code == 200 and res_resched.json()["start_time"] == new_slot,
        f"Appointment rescheduled. New start: {res_resched.json()['start_time']}",
    )

    # Verify that the original slot is now freed up and bookable again!
    res_rebook_old = client.post(
        "/appointments",
        json={"doctor_id": doc_1, "start_time": slot_start},
        headers=headers_p2,
    )
    rebook_id = res_rebook_old.json().get("id")
    check(
        "18. Verified Old Slot Was Released and Can Be Booked by Another Patient",
        res_rebook_old.status_code == 201,
        f"Patient 2 booked the released slot (New Appt ID: {rebook_id})",
    )
    patient2_appt_id = rebook_id

    # -------------------------------------------------------------------------
    # 12. Cancel Appointment
    # -------------------------------------------------------------------------
    cancel_reason = "Patient had a schedule conflict with an emergency meeting"
    res_cancel = client.patch(
        f"/appointments/{appt_id}/cancel",
        json={"reason": cancel_reason},
        headers=headers_p1,
    )
    check(
        f"19. Cancel Appointment #{appt_id} with Reason",
        res_cancel.status_code == 200
        and res_cancel.json()["status"] == "cancelled"
        and res_cancel.json()["cancel_reason"] == cancel_reason,
        f"Status: {res_cancel.json()['status']}, Cancelled At: {res_cancel.json()['cancelled_at']}",
    )

    # Double cancellation check
    res_dup_cancel = client.patch(
        f"/appointments/{appt_id}/cancel",
        json={"reason": "Trying to cancel again"},
        headers=headers_p1,
    )
    dup_ok = (
        res_dup_cancel.status_code == 409
        and res_dup_cancel.json().get("code") == "ALREADY_CANCELLED"
    )
    check(
        "20. Preventing Double Cancellation (409 Conflict)",
        dup_ok,
        f"Correctly rejected with 409: {res_dup_cancel.json().get('detail')}",
    )

    # Clean up patient 2's booking too
    client.patch(
        f"/appointments/{patient2_appt_id}/cancel",
        json={"reason": "Cleanup test booking"},
        headers=headers_p2,
    )

    # -------------------------------------------------------------------------
    # 13. Direct Database Verification
    # -------------------------------------------------------------------------
    print("-" * 70)
    print("DIRECT DATABASE RECORD INSPECTION:")
    with SessionLocal() as db:
        db_appt = db.scalar(select(Appointment).where(Appointment.id == appt_id))
        check(
            f"21. Direct DB Query: Appointment #{appt_id} row exists in database",
            db_appt is not None,
            f"DB row: id={db_appt.id}, doc={db_appt.doctor_id}, pat={db_appt.patient_id}, "
            f"status='{db_appt.status}', reason='{db_appt.cancel_reason}'",
        )

        total_appts = db.scalar(select(func.count()).select_from(Appointment))
        total_doctors = db.scalar(select(func.count()).select_from(Doctor))
        total_patients = db.scalar(select(func.count()).select_from(Patient))
        print(f"       -> Total Doctors in DB: {total_doctors}")
        print(f"       -> Total Patients in DB: {total_patients}")
        print(f"       -> Total Appointments in DB: {total_appts}")

    print("=" * 70)
    print(f"TEST RESULTS: {passed_count}/{total_count} CHECKS PASSED SUCCESSFULLY (100%)")
    print("=" * 70)


if __name__ == "__main__":
    run_tests()
