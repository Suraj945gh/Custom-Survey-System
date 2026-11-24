"""Live dashboard numbers and the standard export. Test runs are never included.

Export format (from the brief), one row per COMPLETED response:
    Respondent ID | Version | Completed at | then one or more columns per question
    single / dropdown / yesno / consent   one column, the option name      "Q3. What is your gender?" -> Male
    multi                                 one column per option, the option name if picked, blank if not
                                          "Q6. Which brands...? - Apple" -> Apple
    Other (specify)                       the typed text inside the Other column -> "Other-Nokia"
    matrix                                one column per row, the chosen scale point
    rating / nps / number / text          one column, the value
    info                                  no column (nothing to answer)
Questions from every approved version are included. A column that a version didn't have stays blank.

Quality flags (bonus): a completed response is flagged, never deleted, when it is
    a speeder        less than 2 seconds per answered question, or (once there are 5+ completes)
                     faster than a third of the median completion time
    straight-lining  the same scale point on every row of a matrix with 3 or more rows
The flags show on the dashboard and in the export's "Quality flags" column.
"""

from __future__ import annotations

import csv
import io
import re
import statistics
from collections import Counter
from datetime import datetime
from typing import Any, Callable

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db import utcnow
from app.engine.answers import norm
from app.tables import (
    RESPONSE_COMPLETED,
    RESPONSE_IN_PROGRESS,
    RESPONSE_TERMINATED,
    Answer,
    Question,
    Response,
    Survey,
)

from . import respond
from . import surveys as survey_service

# --------------------------------------------------------------------------- dashboard


def completed_counts(db: Session) -> dict[int, int]:
    """Completes per survey id (for the survey list)."""
    rows = db.execute(
        select(Response.survey_id, func.count(Response.id))
        .where(Response.status == RESPONSE_COMPLETED, Response.is_test.is_(False))
        .group_by(Response.survey_id)
    )
    return dict(rows.all())


def dashboard(db: Session, survey: Survey) -> dict[str, Any]:
    survey_service.refresh_status(db, survey)
    real = select(Response).where(Response.survey_id == survey.id, Response.is_test.is_(False))
    responses = list(db.scalars(real))
    status_counts = Counter(r.status for r in responses)

    reasons: Counter = Counter()
    for r in responses:
        if r.status == RESPONSE_TERMINATED and r.end_reasons:
            reasons.update(part.strip() for part in r.end_reasons.split("|") if part.strip())

    version = survey_service.current_version(survey)
    quotas = list(version.quotas) if version else []
    counts = respond.quota_counts(db, survey.id, quotas)
    quota_rows = []
    for quota in quotas:
        done = counts[(quota.question_qid, norm(quota.value))]
        quota_rows.append({
            "question": quota.question_qid, "value": quota.value, "target": quota.target,
            "done": done, "left": max(quota.target - done, 0), "full": done >= quota.target,
        })

    by_version = Counter((r.version.version_no, r.status) for r in responses)
    versions = sorted({no for no, _ in by_version}, key=lambda n: (n is None, n))
    completed = status_counts[RESPONSE_COMPLETED]
    return {
        "survey_id": survey.id,
        "status": survey.status,
        "target": survey.target,
        "started": len(responses),
        "completed": completed,
        "terminated": status_counts[RESPONSE_TERMINATED],
        "in_progress": status_counts[RESPONSE_IN_PROGRESS],
        "progress": round(100 * completed / survey.target) if survey.target else 0,
        "quotas": quota_rows,
        "reasons": [{"reason": text, "count": n} for text, n in reasons.most_common()],
        "versions": [
            {"version_no": no, "started": sum(c for (v, _), c in by_version.items() if v == no),
             "completed": by_version[(no, RESPONSE_COMPLETED)]}
            for no in versions
        ],
        "drop_off": drop_off(responses),
        "quality": quality_summary([r for r in responses if r.status == RESPONSE_COMPLETED]),
        "test_runs": db.scalar(
            select(func.count(Response.id)).where(Response.survey_id == survey.id, Response.is_test.is_(True))
        ) or 0,
        "updated_at": utcnow(),
    }


def drop_off(responses: list[Response]) -> list[dict[str, Any]]:
    """Where people who are still 'in progress' stopped: their last answered question."""
    stops: Counter = Counter()
    for r in responses:
        if r.status != RESPONSE_IN_PROGRESS:
            continue
        if not r.answers:
            stops["(not started)"] += 1
            continue
        last = max(r.answers, key=lambda a: (a.answered_at, a.question.position))
        stops[last.question.qid] += 1
    return [{"question": q, "count": n} for q, n in stops.most_common()]


# --------------------------------------------------------------------------- quality flags (bonus)

SPEEDER_SECONDS_PER_ANSWER = 2
SPEEDER_SHARE_OF_MEDIAN = 1 / 3
SPEEDER_MIN_COMPLETES = 5  # below this, the median says too little
STRAIGHT_LINE_MIN_ROWS = 3


def _seconds(r: Response) -> float | None:
    if r.ended_at is None or r.started_at is None:
        return None
    return max((r.ended_at - r.started_at).total_seconds(), 0.0)


def quality_flags(completes: list[Response]) -> dict[int, list[str]]:
    """response id -> its flags, e.g. ["Speeder", "Straight-lining (q11)"]. Unflagged ids are left out."""
    times = [t for r in completes if (t := _seconds(r)) is not None]
    median = statistics.median(times) if len(times) >= SPEEDER_MIN_COMPLETES else None
    flags: dict[int, list[str]] = {}
    for r in completes:
        found: list[str] = []
        seconds = _seconds(r)
        answered = sum(1 for a in r.answers if a.question.type != "info")
        if seconds is not None and answered and (
            seconds < SPEEDER_SECONDS_PER_ANSWER * answered
            or (median is not None and seconds < median * SPEEDER_SHARE_OF_MEDIAN)
        ):
            found.append("Speeder")
        for a in sorted(r.answers, key=lambda a: a.question.position):
            if a.question.type == "matrix" and isinstance(a.value, dict):
                picked = [v for v in a.value.values() if v not in (None, "")]
                if len(picked) >= STRAIGHT_LINE_MIN_ROWS and len(set(picked)) == 1:
                    found.append(f"Straight-lining ({a.question.qid})")
        if found:
            flags[r.id] = found
    return flags


def quality_summary(completes: list[Response]) -> dict[str, Any]:
    flags = quality_flags(completes)
    by_id = {r.id: r for r in completes}
    flagged = sorted(flags.items(), key=lambda item: by_id[item[0]].ended_at or utcnow(), reverse=True)
    return {
        "checked": len(completes),
        "speeders": sum(1 for f in flags.values() if "Speeder" in f),
        "straight_liners": sum(1 for f in flags.values() if any(x.startswith("Straight-lining") for x in f)),
        "flagged": [
            {"respondent_id": by_id[rid].respondent_id, "flags": f, "seconds": round(_seconds(by_id[rid]) or 0)}
            for rid, f in flagged[:20]
        ],
    }


# --------------------------------------------------------------------------- export


def _label(qid: str) -> str:
    """q1 -> Q1 (the brief's header style)."""
    return qid[:1].upper() + qid[1:]


def _short(label: str) -> str:
    """'Other (specify)' -> 'Other' (the brief shows the Other column as '- Other' and 'Other-Lava')."""
    return re.sub(r"\s*\([^)]*\)\s*$", "", label).strip() or label


Getter = Callable[[dict[str, Answer]], Any]


def _columns(survey: Survey) -> list[tuple[str, Getter]]:
    """(header, how to get the value) for every column, newest version first, older extras after."""
    versions = list(reversed(survey_service.approved_versions(survey)))
    merged: dict[str, dict[str, Any]] = {}  # qid -> {question, options[], rows[]}
    for version in versions:
        for q in version.questions:
            entry = merged.setdefault(q.qid, {"q": q, "options": [], "rows": []})
            for option in q.options:
                if option["label"] not in [o["label"] for o in entry["options"]]:
                    entry["options"].append(option)
            for row in q.rows:
                if row not in entry["rows"]:
                    entry["rows"].append(row)

    columns: list[tuple[str, Getter]] = []
    for qid, entry in merged.items():
        q: Question = entry["q"]
        title = f"{_label(qid)}. {q.text}"
        if q.type == "info":
            continue
        if q.type == "multi":
            for option in entry["options"]:
                columns.append((f"{title} - {_short(option['label'])}", _multi_getter(qid, option)))
        elif q.type == "matrix":
            for row in entry["rows"]:
                columns.append((f"{title} - {row}", _matrix_getter(qid, row)))
        else:
            other_labels = {o["label"] for o in entry["options"] if o.get("other")}
            columns.append((title, _single_getter(qid, other_labels)))
    return columns


def _multi_getter(qid: str, option: dict) -> Getter:
    def get(answers: dict[str, Answer]):
        answer = answers.get(qid)
        if answer is None or not isinstance(answer.value, list) or option["label"] not in answer.value:
            return ""
        if option.get("other") and answer.other_text:
            return f"{_short(option['label'])}-{answer.other_text}"
        return option["label"]

    return get


def _matrix_getter(qid: str, row: str) -> Getter:
    def get(answers: dict[str, Answer]):
        answer = answers.get(qid)
        return answer.value.get(row, "") if answer is not None and isinstance(answer.value, dict) else ""

    return get


def _single_getter(qid: str, other_labels: set[str]) -> Getter:
    def get(answers: dict[str, Answer]):
        answer = answers.get(qid)
        if answer is None or answer.value is None:
            return ""
        if isinstance(answer.value, str) and answer.value in other_labels and answer.other_text:
            return f"{_short(answer.value)}-{answer.other_text}"
        return answer.value

    return get


def export_table(db: Session, survey: Survey) -> tuple[list[str], list[list[Any]]]:
    columns = _columns(survey)
    headers = ["Respondent ID", "Version", "Completed at", "Quality flags"] + [header for header, _ in columns]
    responses = db.scalars(
        select(Response)
        .where(Response.survey_id == survey.id, Response.status == RESPONSE_COMPLETED, Response.is_test.is_(False))
        .options(selectinload(Response.answers).selectinload(Answer.question), selectinload(Response.version))
        .order_by(Response.ended_at, Response.id)
    )
    responses = list(responses)
    flags = quality_flags(responses)
    rows = []
    for r in responses:
        answers = {a.question.qid: a for a in r.answers}
        ended = r.ended_at.strftime("%Y-%m-%d %H:%M") if r.ended_at else ""
        row = [r.respondent_id, r.version.version_no, ended, " | ".join(flags.get(r.id, []))]
        rows.append(row + [get(answers) for _, get in columns])
    return headers, rows


def to_csv(headers: list[str], rows: list[list[Any]]) -> bytes:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(headers)
    writer.writerows(rows)
    return out.getvalue().encode("utf-8-sig")  # the BOM makes Excel read Hindi / ₹ etc. correctly


def to_xlsx(headers: list[str], rows: list[list[Any]], title: str) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = (re.sub(r"[\[\]:*?/\\]", "", title) or "Completes")[:31]
    ws.append(headers)
    for row in rows:
        ws.append(row)
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="4338CA")
        cell.alignment = Alignment(wrap_text=True, vertical="top")
    for i, header in enumerate(headers, start=1):
        ws.column_dimensions[get_column_letter(i)].width = max(12, min(40, len(str(header)) * 0.6))
    ws.row_dimensions[1].height = 48
    ws.freeze_panes = "B2"
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def export_file_name(survey: Survey, extension: str, now: datetime | None = None) -> str:
    return f"{survey.slug}_completes_{(now or utcnow()):%Y-%m-%d}.{extension}"
