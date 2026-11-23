"""Respondents: join with a phone number, answer one screen at a time, see an end screen.

    join          phone -> personal link token. Same phone + same survey = the same link back.
                  Completed any survey in the last 90 days -> not eligible yet (decision D7).
    open_link     reopening the link resumes at the first unanswered question.
    show_question Back: show an earlier question with its saved answer.
    submit        check the answer, save it at once, then ask the engine what happens next.

Every answer is written to the database the moment it is submitted, so a dead phone loses
nothing. The response stays on the version it started on (decision D4).
"""

from __future__ import annotations

import random
from collections import Counter
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.db import utcnow
from app.engine import AnswerError, Given, SurveyEngine, clean_answer, join_reasons, matches, normalise_phone
from app.engine.answers import norm
from app.security import new_link_token
from app.tables import (
    CLOSED_BY_TEAM,
    CLOSED_DEADLINE,
    CLOSED_TARGET,
    RESPONSE_COMPLETED,
    RESPONSE_TERMINATED,
    SURVEY_CLOSED,
    SURVEY_LIVE,
    Answer,
    Question,
    Respondent,
    Response,
    Survey,
    SurveyVersion,
)

from . import surveys as survey_service
from .errors import ServiceError, conflict, not_found

COOL_OFF_DAYS = 90
_rng = random.SystemRandom()  # shuffle order per respondent

CLOSED_MESSAGES = {
    CLOSED_TARGET: "We have received all the responses we needed. Thank you for your interest.",
    CLOSED_DEADLINE: "The deadline for this survey has passed.",
    CLOSED_BY_TEAM: "The research team has closed this survey.",
}
END_TEXTS = {
    "completed": ("Thank you!", "Your answers have been saved. You can close this page."),
    "already_completed": ("You have already taken part", "Thank you, your answers are saved. You can close this page."),
    "not_eligible": ("Thank you for your time", "This survey is looking for a different group of people, so it ends here."),
    "closed": ("This survey is closed", ""),
}


# --------------------------------------------------------------------------- joining


def _live_survey_by_slug(db: Session, slug: str) -> Survey:
    survey = db.scalar(select(Survey).where(Survey.slug == slug))
    if survey is None or (survey.status != SURVEY_LIVE and survey.live_at is None):
        raise not_found("Survey")  # drafts that never went live are invisible to the public
    return survey_service.refresh_status(db, survey)


def public_info(db: Session, slug: str) -> dict[str, Any]:
    survey = _live_survey_by_slug(db, slug)
    is_open = survey.status == SURVEY_LIVE
    return {
        "slug": survey.slug,
        "title": survey.title,
        "open": is_open,
        "message": None if is_open else CLOSED_MESSAGES.get(survey.closed_reason or "", CLOSED_MESSAGES[CLOSED_BY_TEAM]),
    }


def join(db: Session, slug: str, phone: str, now: datetime | None = None) -> dict[str, Any]:
    now = now or utcnow()
    survey = _live_survey_by_slug(db, slug)
    number = normalise_phone(phone)
    if number is None:
        raise ServiceError("Please enter a valid 10-digit mobile number.", 422)

    respondent = db.scalar(select(Respondent).where(Respondent.phone == number))
    if respondent is not None:
        existing = db.scalar(select(Response).where(Response.survey_id == survey.id, Response.respondent_id == respondent.id))
        if existing is not None:
            return {"token": existing.token, "resumed": True}  # same person, same survey: same link

    if survey.status != SURVEY_LIVE:
        raise ServiceError(CLOSED_MESSAGES.get(survey.closed_reason or "", CLOSED_MESSAGES[CLOSED_BY_TEAM]), 409,
                           extra={"code": "closed"})

    if respondent is not None:
        last = db.scalar(
            select(func.max(Response.ended_at)).where(
                Response.respondent_id == respondent.id,
                Response.status == RESPONSE_COMPLETED,
                Response.is_test.is_(False),
            )
        )
        if last is not None and last > now - timedelta(days=COOL_OFF_DAYS):
            eligible_from = last + timedelta(days=COOL_OFF_DAYS)
            raise ServiceError(
                f"You took part in one of our surveys recently. You can join again from {eligible_from:%d %b %Y}.",
                403,
                extra={"code": "cool_off", "eligible_from": eligible_from.isoformat()},
            )
    else:
        respondent = Respondent(phone=number)
        db.add(respondent)

    version = survey_service.current_version(survey)
    response = Response(token=new_link_token(), survey=survey, version=version, respondent=respondent)
    db.add(response)
    db.commit()
    return {"token": response.token, "resumed": False}


def start_test_run(db: Session, survey: Survey, use_draft: bool | None = None) -> dict[str, Any]:
    """Preview / test mode: a response flagged is_test, never counted anywhere."""
    draft = survey_service.draft_of(survey)
    if use_draft is None:
        use_draft = draft is not None
    version: SurveyVersion | None = draft if use_draft else survey_service.current_version(survey)
    if version is None:
        raise conflict("There is no draft to preview." if use_draft else "There is no approved version to preview.")
    if not version.questions:
        raise conflict("Fix the errors in the draft before previewing it.")
    response = Response(token=new_link_token(), survey=survey, version=version, is_test=True)
    db.add(response)
    db.commit()
    return {"token": response.token, "version_no": version.version_no, "is_draft": version.is_draft}


# --------------------------------------------------------------------------- the respondent's screens


def _response(db: Session, token: str) -> Response:
    response = db.scalar(select(Response).where(Response.token == token))
    if response is None:
        raise ServiceError("This survey link is not valid. Please check the link you were sent.", 404)
    return response


def _engine(response: Response) -> SurveyEngine:
    return SurveyEngine(response.version.questions, response.version.quotas)


def _answers(response: Response) -> dict[str, Given]:
    return {a.question.qid: Given(a.value, a.other_text) for a in response.answers}


def open_link(db: Session, token: str) -> dict[str, Any]:
    """Reopen the link: resume at the first unanswered question."""
    response = _response(db, token)
    if (gate := _gate(db, response)) is not None:
        return gate
    engine, answers = _engine(response), _answers(response)
    walk = engine.walk(answers)
    if walk.current is None:  # everything answered but not finished (e.g. the phone died at the last tap)
        return _finish(db, response, engine, answers)
    return _question_screen(db, response, engine, answers, walk.current)


def show_question(db: Session, token: str, qid: str) -> dict[str, Any]:
    """Go Back: show an earlier question on this person's path, with the saved answer."""
    response = _response(db, token)
    if (gate := _gate(db, response)) is not None:
        return gate
    engine, answers = _engine(response), _answers(response)
    if qid not in engine.by_id:
        raise not_found("Question")
    if qid not in engine.walk(answers).path:
        raise conflict("This question is not available yet.")
    return _question_screen(db, response, engine, answers, qid)


def submit(db: Session, token: str, qid: str, value: Any, other_text: Any = None) -> dict[str, Any]:
    response = _response(db, token)
    if (gate := _gate(db, response)) is not None:
        return gate
    engine, answers = _engine(response), _answers(response)
    walk = engine.walk(answers)
    if qid not in walk.path:
        raise conflict("This question is not available right now. Please reload the page.")

    q = engine.by_id[qid]
    try:
        given = clean_answer(q, value, other_text, engine.options_for(q, walk.active))
    except AnswerError as exc:
        raise ServiceError(str(exc), 422, extra={"code": "invalid_answer"}) from None

    answers[qid] = given
    removed = engine.tidy(answers)  # answers that no longer count after this change
    _save(db, response, qid, given, removed)

    outcome = engine.after_answer(qid, answers, full_quota_groups(db, response.survey_id, engine.quotas))
    if outcome.kind == "terminated":
        _end(response, RESPONSE_TERMINATED, join_reasons(outcome.reasons), silent=outcome.silent)
        db.commit()
        return _end_screen(response, "completed" if outcome.silent else "not_eligible")
    if outcome.kind == "complete":
        return _finish(db, response, engine, answers)
    db.commit()
    return _question_screen(db, response, engine, answers, outcome.next_qid)


# --------------------------------------------------------------------------- helpers


def _gate(db: Session, response: Response) -> dict[str, Any] | None:
    """An end screen if this response can't continue, otherwise None."""
    if response.status == RESPONSE_COMPLETED:
        return _end_screen(response, "already_completed")
    if response.status == RESPONSE_TERMINATED:
        return _end_screen(response, "already_completed" if response.silent_end else "not_eligible")
    if response.is_test:
        return None  # previews work whatever the survey's status
    survey = survey_service.refresh_status(db, response.survey)
    if survey.status != SURVEY_LIVE:
        # Decision D5: the partial answers are kept (still "in progress", never counted).
        return _end_screen(response, "closed")
    return None


def _save(db: Session, response: Response, qid: str, given: Given, removed: set[str]) -> None:
    by_qid = {a.question.qid: a for a in response.answers}
    question_ids = {q.qid: q.id for q in response.version.questions}
    row = by_qid.get(qid)
    if row is None:
        response.answers.append(Answer(question_id=question_ids[qid], value=given.value, other_text=given.other_text))
    else:
        row.value, row.other_text, row.answered_at = given.value, given.other_text, utcnow()
    for old in removed:
        if old in by_qid:
            response.answers.remove(by_qid[old])
    response.updated_at = utcnow()
    db.flush()  # the write lock is taken here, so finishing below is one transaction


def _finish(db: Session, response: Response, engine: SurveyEngine, answers: dict[str, Given]) -> dict[str, Any]:
    """Last question answered: check quotas once more inside the same transaction, then complete."""
    survey = response.survey
    if not response.is_test:
        # A no-op write: in SQLite this takes the write lock, so two people finishing at the same
        # moment are handled one after the other and can't both take the last quota place.
        db.execute(update(Survey).where(Survey.id == survey.id).values(status=Survey.status))
        if survey.status != SURVEY_LIVE or (survey.deadline is not None and survey.deadline <= utcnow()):
            survey_service.refresh_status(db, survey)
            db.commit()
            return _end_screen(response, "closed")

    walk = engine.walk(answers)
    reasons = engine.end_reasons(walk.active, full_quota_groups(db, survey.id, engine.quotas))
    if reasons:
        silent = all(r.silent for r in reasons)
        _end(response, RESPONSE_TERMINATED, join_reasons(reasons), silent=silent)
        db.commit()
        return _end_screen(response, "completed" if silent else "not_eligible")

    _end(response, RESPONSE_COMPLETED, None)
    db.flush()
    if not response.is_test and survey.target and completes(db, survey.id) >= survey.target:
        survey.status, survey.closed_reason, survey.closed_at = SURVEY_CLOSED, CLOSED_TARGET, utcnow()
    db.commit()
    return _end_screen(response, "completed")


def _end(response: Response, status: str, reasons: str | None, silent: bool = False) -> None:
    response.status = status
    response.end_reasons = reasons
    response.silent_end = silent
    response.ended_at = utcnow()


def _question_screen(db: Session, response: Response, engine: SurveyEngine, answers: dict[str, Given], qid: str):
    walk = engine.walk(answers)
    q = engine.by_id[qid]
    saved = (response.option_orders or {}).get(qid)
    options, new_order = engine.ordered_options(q, walk.active, saved, _rng)
    if new_order is not None:
        response.option_orders = {**(response.option_orders or {}), qid: new_order}  # new dict: JSON change is saved
        db.commit()
    given = answers.get(qid)
    return {
        "kind": "question",
        "survey_title": response.survey.title,
        "is_test": response.is_test,
        "progress": engine.progress(qid),
        "previous_qid": engine.previous_before(qid, walk),
        "question": engine.render(q, walk.active, options),
        "answer": {"value": given.value, "other_text": given.other_text} if given else None,
    }


def _end_screen(response: Response, kind: str) -> dict[str, Any]:
    title, message = END_TEXTS[kind]
    if kind == "closed":
        message = CLOSED_MESSAGES.get(response.survey.closed_reason or "", CLOSED_MESSAGES[CLOSED_BY_TEAM])
    screen = {
        "kind": "end",
        "survey_title": response.survey.title,
        "is_test": response.is_test,
        "end": kind,
        "title": title,
        "message": message,
        "progress": 100 if kind in ("completed", "already_completed", "not_eligible") else None,
    }
    if response.is_test:
        screen["reasons"] = response.end_reasons  # testers see why it ended; real respondents don't
    return screen


# --------------------------------------------------------------------------- counting (real responses only)


def completes(db: Session, survey_id: int) -> int:
    return db.scalar(
        select(func.count(Response.id)).where(
            Response.survey_id == survey_id, Response.status == RESPONSE_COMPLETED, Response.is_test.is_(False)
        )
    ) or 0


def quota_counts(db: Session, survey_id: int, quotas) -> Counter:
    """Completed (non-test) responses per quota group, keyed by (question id, value)."""
    qids = {quota.question_qid for quota in quotas}
    counts: Counter = Counter()
    if not qids:
        return counts
    rows = db.execute(
        select(Question.qid, Answer.value, Answer.other_text)
        .join(Answer, Answer.question_id == Question.id)
        .join(Response, Answer.response_id == Response.id)
        .where(
            Response.survey_id == survey_id,
            Response.status == RESPONSE_COMPLETED,
            Response.is_test.is_(False),
            Question.qid.in_(qids),
        )
    )
    for qid, value, other in rows:
        for quota in quotas:
            if quota.question_qid == qid and matches(value, other, quota.value):
                counts[(qid, norm(quota.value))] += 1
    return counts


def full_quota_groups(db: Session, survey_id: int, quotas) -> set[tuple[str, str]]:
    counts = quota_counts(db, survey_id, quotas)
    return {(q.question_qid, norm(q.value)) for q in quotas if counts[(q.question_qid, norm(q.value))] >= q.target}
