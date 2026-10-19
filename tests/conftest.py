import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from collections.abc import Iterator  # noqa: E402
from datetime import time  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.database import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base, Doctor, Patient, WorkingHours  # noqa: E402


@pytest.fixture
def engine():
    eng = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    @event.listens_for(eng, "connect")
    def _fk_on(dbapi_conn, _):  # SQLite ignores FKs unless asked
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(eng)
    return eng


@pytest.fixture
def session(engine) -> Iterator[Session]:
    with sessionmaker(bind=engine)() as s:
        yield s


@pytest.fixture
def doctor(session: Session) -> Doctor:
    d = Doctor(name="Dr. Test")
    session.add(d)
    session.commit()
    return d


@pytest.fixture
def doctor_with_schedule(session: Session) -> Doctor:
    d = Doctor(name="Dr. Schedule", specialty="General Practice")
    for weekday in range(0, 5):  # Mon-Fri
        d.working_hours.append(
            WorkingHours(weekday=weekday, start_time=time(8, 0), end_time=time(12, 0))
        )
        d.working_hours.append(
            WorkingHours(weekday=weekday, start_time=time(13, 0), end_time=time(17, 0))
        )
    session.add(d)
    session.commit()
    return d


@pytest.fixture
def patient(session: Session) -> Patient:
    p = Patient(name="Pat", email="pat@example.com")
    session.add(p)
    session.commit()
    return p


@pytest.fixture
def second_patient(session: Session) -> Patient:
    p = Patient(name="Pat Two", email="pat2@example.com")
    session.add(p)
    session.commit()
    return p


@pytest.fixture
def auth_headers(patient: Patient) -> dict[str, str]:
    from app.auth import create_access_token
    from app.config import get_settings

    token = create_access_token(patient.id, patient.email, get_settings())
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers_second(second_patient: Patient) -> dict[str, str]:
    from app.auth import create_access_token
    from app.config import get_settings

    token = create_access_token(second_patient.id, second_patient.email, get_settings())
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client(session: Session) -> Iterator[TestClient]:
    def _override_get_db() -> Iterator[Session]:
        yield session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
