import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from collections.abc import Iterator  # noqa: E402

import pytest  # noqa: E402
from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.models import Base, Doctor, Patient  # noqa: E402


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
def patient(session: Session) -> Patient:
    p = Patient(name="Pat", email="pat@example.com")
    session.add(p)
    session.commit()
    return p
