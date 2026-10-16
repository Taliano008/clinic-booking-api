"""Idempotent seed: 5 doctors with realistic schedules + 3 demo patients.

Run with:  python -m scripts.seed
Safe to run on every deploy - it does nothing if doctors already exist.
"""

from datetime import time

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Doctor, Patient, WorkingHours

MORNING = (time(8, 0), time(12, 0))
AFTERNOON = (time(13, 0), time(17, 0))  # 12:00-13:00 lunch gap is simply "no rows"

DOCTORS: list[tuple[str, str, dict[int, list[tuple[time, time]]]]] = [
    ("Dr. Amina Wanjiru", "General Practice", {d: [MORNING, AFTERNOON] for d in range(0, 5)}),
    ("Dr. Brian Otieno", "Pediatrics", {d: [MORNING, AFTERNOON] for d in range(0, 5)}),
    ("Dr. Cynthia Mwangi", "Dermatology", {d: [(time(9, 0), time(15, 0))] for d in (0, 2, 4)}),
    ("Dr. David Kamau", "Cardiology", {d: [(time(10, 0), time(18, 0))] for d in range(1, 5)}),
    (
        "Dr. Esther Njeri",
        "General Practice",
        {**{d: [MORNING] for d in range(0, 5)}, 5: [(time(9, 0), time(13, 0))]},  # works Saturdays
    ),
]

PATIENTS = [
    ("Test Patient One", "patient1@example.com", "+254700000001"),
    ("Test Patient Two", "patient2@example.com", "+254700000002"),
    ("Test Patient Three", "patient3@example.com", "+254700000003"),
]


def seed(session: Session) -> bool:
    if session.scalar(select(func.count()).select_from(Doctor)):
        return False
    for name, specialty, schedule in DOCTORS:
        doctor = Doctor(name=name, specialty=specialty)
        for weekday, blocks in schedule.items():
            for start, end in blocks:
                doctor.working_hours.append(
                    WorkingHours(weekday=weekday, start_time=start, end_time=end)
                )
        session.add(doctor)
    session.add_all(Patient(name=n, email=e, phone=p) for n, e, p in PATIENTS)
    session.commit()
    return True


if __name__ == "__main__":
    with SessionLocal() as s:
        print("Seeded." if seed(s) else "Already seeded - nothing to do.")
