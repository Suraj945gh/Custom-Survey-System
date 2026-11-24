"""Demo data:  python -m app.seed          (adds what is missing, safe to run twice)
               python -m app.seed --reset  (wipes the database first)

Creates:
    admin@demo.local       / admin12345     (admin)
    researcher@demo.local  / research12345  (researcher)
    smartphone_study  sample questionnaire, approved as v1 and live (deadline +15 days),
                      with 42 made-up respondents so the dashboard and export have data
    snack_study       the broken questionnaire as a draft, so the error list can be shown
"""

from __future__ import annotations

import argparse
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import Base, SessionLocal, create_tables, engine
from app.demo_responses import add_demo_responses
from app.services import surveys as survey_service
from app.services import users as user_service
from app.tables import ROLE_ADMIN, ROLE_RESEARCHER, SURVEY_LIVE, Response, Survey, User

SAMPLES = Path(__file__).resolve().parents[2] / "samples"

DEMO_USERS = [
    ("admin@demo.local", "Asha Admin", ROLE_ADMIN, "admin12345"),
    ("researcher@demo.local", "Ravi Researcher", ROLE_RESEARCHER, "research12345"),
]


def seed(db: Session, demo_responses: bool = True) -> list[str]:
    """Add demo users and surveys that are not there yet. Returns what was done, for printing."""
    done: list[str] = []
    for email, name, role, password in DEMO_USERS:
        if db.scalar(select(User).where(User.email == email)) is None:
            user_service.create_user(db, email, name, role, password)
            done.append(f"user {email} ({role}) / password {password}")
    admin = db.scalar(select(User).where(User.email == DEMO_USERS[0][0]))
    researcher = db.scalar(select(User).where(User.email == DEMO_USERS[1][0]))

    if db.scalar(select(Survey).where(Survey.slug == "smartphone_study")) is None:
        text = (SAMPLES / "concave_sample_questionnaire.txt").read_text(encoding="utf-8")
        survey, _ = survey_service.save_draft(db, text, researcher, "concave_sample_questionnaire.txt")
        survey_service.approve(db, survey, admin)
        survey_service.go_live(db, survey)
        done.append("survey smartphone_study: approved as v1 and live")

    smartphone = db.scalar(select(Survey).where(Survey.slug == "smartphone_study"))
    has_responses = db.scalar(select(Response.id).where(Response.survey_id == smartphone.id).limit(1)) is not None
    if demo_responses and smartphone.status == SURVEY_LIVE and not has_responses:
        added = add_demo_responses(db, smartphone)
        done.append(f"survey smartphone_study: {added} demo respondents (completes, screen-outs, half-way)")

    if db.scalar(select(Survey).where(Survey.slug == "snack_study")) is None:
        text = (SAMPLES / "concave_broken_questionnaire.txt").read_text(encoding="utf-8")
        survey_service.save_draft(db, text, researcher, "concave_broken_questionnaire.txt")
        done.append("survey snack_study: draft with errors (to show the upload check)")
    return done


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.seed", description="Load demo data.")
    parser.add_argument("--reset", action="store_true", help="delete all data first")
    parser.add_argument("--no-responses", action="store_true", help="don't add the made-up respondents")
    args = parser.parse_args(argv)

    if args.reset:
        from app import tables  # noqa: F401

        Base.metadata.drop_all(engine)
        print("Database wiped.")
    create_tables()
    with SessionLocal() as db:
        done = seed(db, demo_responses=not args.no_responses)
    print("\n".join(f"  + {line}" for line in done) if done else "  Demo data already present; nothing to add.")


if __name__ == "__main__":
    main()
