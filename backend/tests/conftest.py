import os
from pathlib import Path

# Tests always use a throw-away in-memory database, never the real survey.db.
# This must run before anything from `app` reads the settings.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["PASSWORD_ITERATIONS"] = "1000"  # real hashing is slow on purpose; tests don't need that

import pytest  # noqa: E402

SAMPLES = Path(__file__).resolve().parents[2] / "samples"


@pytest.fixture
def sample_text() -> str:
    return (SAMPLES / "concave_sample_questionnaire.txt").read_text(encoding="utf-8")


@pytest.fixture
def broken_text() -> str:
    return (SAMPLES / "concave_broken_questionnaire.txt").read_text(encoding="utf-8")


# --------------------------------------------------------------------------- database + API


@pytest.fixture
def db():
    """A fresh, empty database for every test."""
    from app.db import Base, SessionLocal, create_tables, engine

    Base.metadata.drop_all(engine)
    create_tables()
    with SessionLocal() as session:
        yield session


@pytest.fixture
def client(db):
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


def _user(db, email, role):
    from app.services.users import create_user

    return create_user(db, email, role.title(), role, "password123")


@pytest.fixture
def admin(db):
    return _user(db, "admin@test.local", "admin")


@pytest.fixture
def researcher(db):
    return _user(db, "researcher@test.local", "researcher")


def _headers(user):
    from app.security import make_token

    return {"Authorization": f"Bearer {make_token(user.id)}"}


@pytest.fixture
def admin_headers(admin):
    return _headers(admin)


@pytest.fixture
def researcher_headers(researcher):
    return _headers(researcher)
