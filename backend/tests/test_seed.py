"""Demo data loads, and running it twice adds nothing."""

from sqlalchemy import select

from app.seed import seed
from app.services import reports
from app.tables import Response, Survey, User


def test_seed_creates_users_and_two_surveys(db):
    done = seed(db)
    assert len(done) == 5
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


def test_demo_respondents_fill_the_dashboard(db):
    seed(db)
    sample = db.scalar(select(Survey).where(Survey.slug == "smartphone_study"))
    d = reports.dashboard(db, sample)
    assert d["started"] == 42
    assert d["completed"] > 20 and d["terminated"] > 0 and d["in_progress"] > 0
    assert {r["reason"] for r in d["reasons"]} == {"q4: City not in scope", "q5: Not a smartphone user"}
    assert d["quality"]["speeders"] >= 2 and d["quality"]["straight_liners"] >= 2
    assert all(r.started_at < r.updated_at for r in db.scalars(select(Response)))


def test_seed_without_responses(db):
    seed(db, demo_responses=False)
    assert db.scalar(select(Response.id)) is None
