"""Demo data loads, and running it twice adds nothing."""

from sqlalchemy import select

from app.seed import seed
from app.tables import Survey, User


def test_seed_creates_users_and_two_surveys(db):
    done = seed(db)
    assert len(done) == 4
    assert {u.role for u in db.scalars(select(User))} == {"admin", "researcher"}
    sample = db.scalar(select(Survey).where(Survey.slug == "smartphone_study"))
    assert sample.status == "live" and sample.deadline is not None
    assert [v.version_no for v in sample.versions] == [1]
    assert len(sample.versions[0].questions) == 18
    broken = db.scalar(select(Survey).where(Survey.slug == "snack_study"))
    assert broken.status == "draft" and broken.versions[0].version_no is None


def test_seed_twice_adds_nothing(db):
    seed(db)
    assert seed(db) == []
    assert len(list(db.scalars(select(Survey)))) == 2


def test_demo_login_works(client, db):
    seed(db)
    r = client.post("/api/auth/login", json={"email": "admin@demo.local", "password": "admin12345"})
    assert r.status_code == 200
