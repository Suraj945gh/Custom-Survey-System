"""Survey life cycle: draft -> approve (version N) -> live -> closed.

    save_draft     upload or edit a file. One draft per survey; saving again replaces it.
                   A file whose <survey id> matches an existing survey becomes that survey's draft.
    approve        admin only. Blocked while the draft has errors. Gives it version_no = last + 1
                   and freezes it. Live surveys switch new respondents to it straight away.
    go_live        admin only. Needs an approved version. Deadline defaults to today + 15 days.
    close          admin only, or automatically when the deadline passes (refresh_status).
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import utcnow
from app.questionnaire import Issue, ParseResult, check_questionnaire
from app.questionnaire.spec import survey_spec
from app.questionnaire.validator import ID_PATTERN
from app.tables import (
    CLOSED_BY_TEAM,
    CLOSED_DEADLINE,
    SURVEY_CLOSED,
    SURVEY_DRAFT,
    SURVEY_LIVE,
    Question,
    Quota,
    Response,
    Survey,
    SurveyVersion,
    User,
)

from .errors import ServiceError, conflict, not_found

# --------------------------------------------------------------------------- reading


def get_survey(db: Session, survey_id: int) -> Survey:
    survey = db.get(Survey, survey_id)
    if survey is None:
        raise not_found("Survey")
    return survey


def draft_of(survey: Survey) -> SurveyVersion | None:
    return next((v for v in survey.versions if v.is_draft), None)


def approved_versions(survey: Survey) -> list[SurveyVersion]:
    return sorted((v for v in survey.versions if not v.is_draft), key=lambda v: v.version_no)


def current_version(survey: Survey) -> SurveyVersion | None:
    """The newest approved version: the one new respondents get."""
    versions = approved_versions(survey)
    return versions[-1] if versions else None


def get_version(survey: Survey, version_no: int) -> SurveyVersion:
    version = next((v for v in survey.versions if v.version_no == version_no), None)
    if version is None:
        raise not_found(f"Version {version_no}")
    return version


def check_text(text: str, expected_slug: str | None = None) -> ParseResult:
    """check_questionnaire, plus one extra rule when editing an existing survey:
    the <survey id> must stay the same, otherwise the file belongs to another survey."""
    result = check_questionnaire(text)
    if expected_slug and result.survey is not None and result.survey.sid and result.survey.sid != expected_slug:
        result.issues.insert(
            0,
            Issue(
                result.survey.attrs.line_of("id", result.survey.line),
                f"This draft belongs to survey '{expected_slug}', but the file says id=\"{result.survey.sid}\". "
                "Change it back, or upload the file as a new survey.",
                "survey_id_changed",
            ),
        )
    return result


def refresh_status(db: Session, survey: Survey, now: datetime | None = None) -> Survey:
    """Close a live survey whose deadline has passed. Called whenever a survey is read."""
    now = now or utcnow()
    if survey.status == SURVEY_LIVE and survey.deadline is not None and survey.deadline <= now:
        _close(survey, CLOSED_DEADLINE, survey.deadline)
        db.commit()
    return survey


def list_surveys(db: Session) -> list[Survey]:
    surveys = list(db.scalars(select(Survey).order_by(Survey.created_at.desc(), Survey.id.desc())))
    for survey in surveys:
        refresh_status(db, survey)
    return surveys


# --------------------------------------------------------------------------- drafts


def save_draft(
    db: Session, text: str, user: User, file_name: str | None = None, survey: Survey | None = None
) -> tuple[Survey, SurveyVersion]:
    """Save a file as the draft of a survey (creating the survey if it is new).
    Drafts may contain errors: they are shown, fixed in the editor, and checked again."""
    if survey is None:
        result = check_text(text)
        sid = result.survey.sid if result.survey is not None else None
        if not sid or not ID_PATTERN.match(sid):
            raise ServiceError(
                'The file needs a valid <survey id="..."> before it can be saved, so we know which survey it belongs to.',
                422,
                result.issues,
            )
        survey = db.scalar(select(Survey).where(Survey.slug == sid))
        if survey is None:
            survey = Survey(slug=sid, title=result.survey.title or sid, status=SURVEY_DRAFT, created_by=user)
            db.add(survey)
    result = check_text(text, expected_slug=survey.slug)

    draft = draft_of(survey)
    if draft is None:
        draft = SurveyVersion(survey=survey, file_text=text, file_name=file_name, created_by=user)
        db.add(draft)
    else:
        draft.file_text = text
        draft.file_name = file_name or draft.file_name
        draft.created_by = user

    # The draft's questions are rebuilt on every save. Old preview runs no longer match, so they go too.
    db.flush()
    db.query(Response).filter(Response.version_id == draft.id).delete(synchronize_session=False)
    draft.questions.clear()
    draft.quotas.clear()
    db.flush()
    if result.ok:
        _store_questions(draft, result)
        if not approved_versions(survey):  # never approved: keep the list's title / target in step with the draft
            survey.title = result.survey.title or survey.slug
            survey.target = int(result.survey.target)
    db.commit()
    return survey, draft


def discard_draft(db: Session, survey: Survey) -> bool:
    """Delete the draft. A survey that was never approved is deleted with it. Returns True if so."""
    draft = draft_of(survey)
    if draft is None:
        raise conflict("This survey has no draft to discard.")
    if not approved_versions(survey):
        db.delete(survey)
        db.commit()
        return True
    survey.versions.remove(draft)
    db.commit()
    return False


def _store_questions(version: SurveyVersion, result: ParseResult) -> None:
    spec = survey_spec(result.survey)
    for position, q in enumerate(spec["questions"]):
        version.questions.append(
            Question(
                position=position,
                qid=q["qid"],
                type=q["type"],
                text=q["text"],
                required=q["required"],
                options=q["options"],
                rows=q["rows"],
                rules=q["rules"],
                line=q["line"],
            )
        )
    for quota in spec["quotas"]:
        version.quotas.append(Quota(question_qid=quota["question"], value=quota["value"], target=quota["target"]))


# --------------------------------------------------------------------------- approve, live, close


def approve(db: Session, survey: Survey, user: User) -> SurveyVersion:
    draft = draft_of(survey)
    if draft is None:
        raise conflict("There is no draft to approve. Upload or edit the file first.")
    result = check_text(draft.file_text, expected_slug=survey.slug)
    if result.errors:
        count = len(result.errors)
        raise conflict(f"The draft has {count} error{'s' if count != 1 else ''}. Fix them before approving.", result.errors)
    latest = current_version(survey)
    if latest is not None and latest.file_text.strip() == draft.file_text.strip():
        raise conflict(f"This draft is the same as version {latest.version_no}, so there is nothing new to approve.")

    last_no = db.scalar(select(func.max(SurveyVersion.version_no)).where(SurveyVersion.survey_id == survey.id))
    draft.version_no = (last_no or 0) + 1
    draft.approved_by = user
    draft.approved_at = utcnow()
    survey.title = result.survey.title or survey.slug
    survey.target = int(result.survey.target)
    db.commit()
    return draft


def go_live(db: Session, survey: Survey, deadline: datetime | None = None) -> Survey:
    """Start (or restart) collecting responses. Also used to reopen a closed survey."""
    refresh_status(db, survey)
    if survey.status == SURVEY_LIVE:
        raise conflict("The survey is already live.")
    if current_version(survey) is None:
        raise conflict("Approve a version before going live.")
    now = utcnow()
    deadline = _future(deadline, now) if deadline else now + timedelta(days=settings.default_deadline_days)
    survey.status = SURVEY_LIVE
    survey.deadline = deadline
    survey.live_at = survey.live_at or now
    survey.closed_at = None
    survey.closed_reason = None
    db.commit()
    return survey


def set_deadline(db: Session, survey: Survey, deadline: datetime) -> Survey:
    refresh_status(db, survey)
    if survey.status != SURVEY_LIVE:
        raise conflict("Only a live survey has a deadline. To reopen a closed survey, go live again.")
    survey.deadline = _future(deadline, utcnow())
    db.commit()
    return survey


def close(db: Session, survey: Survey, reason: str = CLOSED_BY_TEAM) -> Survey:
    refresh_status(db, survey)
    if survey.status != SURVEY_LIVE:
        raise conflict("Only a live survey can be closed.")
    _close(survey, reason, utcnow())
    db.commit()
    return survey


def _close(survey: Survey, reason: str, when: datetime) -> None:
    survey.status = SURVEY_CLOSED
    survey.closed_reason = reason
    survey.closed_at = when


def _future(deadline: datetime, now: datetime) -> datetime:
    if deadline.tzinfo is None:
        raise ServiceError("The deadline needs a time zone, e.g. 2026-12-08T18:00:00+05:30.", 422)
    if deadline <= now:
        raise ServiceError("The deadline must be in the future.", 422)
    return deadline
