"""Made-up respondents for the demo, so the dashboard and export are not empty on first run.

They go through the SAME code as real people (join -> submit answer by answer), so every rule
(skip, show-if, termination, quotas) is applied to them. Afterwards their times are spread over
the last few days. The random generator has a fixed seed, so every run gives the same data.

Phones start at 7000000001, so they never clash with a number you type in yourself.
"""

from __future__ import annotations

import random
from datetime import timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.db import utcnow
from app.services import respond
from app.tables import Response, Survey

NAMES = ["Aarav", "Diya", "Kabir", "Meera", "Rohan", "Sana", "Vikram", "Ananya", "Ishaan", "Priya",
         "Arjun", "Neha", "Kunal", "Pooja", "Rahul", "Tara", "Aditya", "Zoya", "Nikhil", "Riya"]
OTHER_BRANDS = ["Nokia", "Motorola", "Realme", "Lava", "Google Pixel"]
UNHAPPY = ["The battery drains too fast.", "It gets slow after a few apps.", "The camera is poor at night."]

# Who the demo people are. Most finish; some are screened out; some stop half-way.
PLAN = (
    ["complete"] * 26
    + ["speeder"] * 2          # finishes in about a minute -> flagged
    + ["straight_line"] * 2    # same answer on every matrix row -> flagged
    + ["other_city"] * 3       # screened out: q4
    + ["no_phone"] * 2         # screened out: q5
    + ["both_out"] * 1         # screened out for two reasons, joined with " | "
    + ["stopped"] * 6          # still in progress (drop-off report)
)


def _answer(question: dict[str, Any], rng: random.Random, kind: str) -> tuple[Any, str | None]:
    """A sensible random answer for any question screen."""
    qtype, qid = question["type"], question["qid"]
    options = question["options"]
    values = [o["value"] for o in options]
    s = question["settings"]

    if qtype == "info":
        return None, None
    if qtype == "consent":
        return "Yes", None
    if qid == "q4" and kind in ("other_city", "both_out"):
        return "Other city", None
    if qid == "q5" and kind in ("no_phone", "both_out"):
        return "No", None
    if qid in ("q4", "q5"):  # everyone else passes the screening questions
        options = [o for o in options if o["value"] != "Other city"]
        values = [o["value"] for o in options]
        if qid == "q5":
            return "Yes", None
    if qtype == "yesno":
        yes = next((v for v in values if v.lower() == "yes"), values[0] if values else "Yes")
        no = next((v for v in values if v.lower() == "no"), "No")
        return (yes if rng.random() < 0.8 else no), None
    if qtype in ("single", "dropdown"):
        pick = rng.choice(options)
        return pick["value"], (rng.choice(OTHER_BRANDS) if pick["other"] else None)
    if qtype == "multi":
        normal = [o for o in options if not o["exclusive"]]
        most = min(int(s.get("max", 3)), len(normal), 3)
        picked = rng.sample(normal, rng.randint(1, max(most, 1)))
        other = next((o for o in picked if o["other"]), None)
        return [o["value"] for o in picked], (rng.choice(OTHER_BRANDS) if other else None)
    if qtype in ("rating", "nps"):
        low, high = int(s.get("min", 0)), int(s.get("max", 10))
        return rng.choices(range(low, high + 1), weights=range(1, high - low + 2))[0], None  # leans positive
    if qtype == "matrix":
        if kind == "straight_line":
            same = rng.choice(values)
            return {row: same for row in question["rows"]}, None
        return {row: rng.choice(values[:3]) for row in question["rows"]}, None
    if qtype == "number":
        low, high = float(s.get("min", 0)), float(s.get("max", 100))
        if high - low > 1000:  # e.g. a budget: round thousands
            return rng.randrange(int(low), int(high) + 1, 1000), None
        return rng.randint(int(low), int(high)), None
    if qtype == "longtext":
        return rng.choice(UNHAPPY), None
    if qtype == "text":
        return rng.choice(NAMES), None
    if qtype == "formatted":
        fmt = s.get("format")
        if fmt == "pincode":
            return f"{rng.choice([400, 411, 110, 560])}{rng.randint(1, 99):03d}", None
        if fmt == "phone":
            return f"9{rng.randint(100000000, 999999999)}", None
        return f"{rng.choice(NAMES).lower()}@example.com", None
    return None, None


def add_demo_responses(db: Session, survey: Survey, seed: int = 7) -> int:
    """Fill a live survey with the PLAN above. Returns how many people were added."""
    rng = random.Random(seed)
    now = utcnow()
    added = 0
    for n, kind in enumerate(PLAN, start=1):
        token = respond.join(db, survey.slug, f"70000{n:05d}")["token"]
        stop_after = rng.randint(4, 12) if kind == "stopped" else None
        screen = respond.open_link(db, token)
        answered = 0
        while screen["kind"] == "question" and (stop_after is None or answered < stop_after):
            question = screen["question"]
            value, other = _answer(question, rng, kind)
            screen = respond.submit(db, token, question["qid"], value, other)
            answered += 1
        _spread_in_time(db, token, now, rng, kind)
        added += 1
    db.commit()
    return added


def _spread_in_time(db: Session, token: str, now, rng: random.Random, kind: str) -> None:
    """Move this person's start, answers and end into the last 4 days, with a realistic duration."""
    response = db.query(Response).filter_by(token=token).one()
    minutes = rng.uniform(0.8, 1.2) if kind == "speeder" else rng.uniform(4, 11)
    start = now - timedelta(days=rng.uniform(0.1, 4)) - timedelta(minutes=minutes)
    answers = sorted(response.answers, key=lambda a: a.question.position)
    step = timedelta(minutes=minutes) / max(len(answers), 1)
    response.started_at = start
    for i, a in enumerate(answers, start=1):
        a.answered_at = start + step * i
    if response.ended_at is not None:
        response.ended_at = start + timedelta(minutes=minutes)
    response.updated_at = (answers[-1].answered_at if answers else start)
