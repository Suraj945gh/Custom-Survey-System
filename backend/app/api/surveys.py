"""Survey routes for staff: check a file, save drafts, approve, go live, close.

Researchers and admins can check, upload, edit and look. Only admins can approve, go live,
change the deadline and close (decision D8).
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.services import reports
from app.services import respond as respond_service
from app.services import surveys as service
from app.tables import Survey, SurveyVersion, User

from .deps import admin_user, current_user
from .schemas import (
    CheckOut,
    DeadlineIn,
    DraftOut,
    GoLiveIn,
    QuestionOut,
    QuotaOut,
    SurveyDetailOut,
    SurveyOut,
    TestRunIn,
    TestRunOut,
    TextIn,
    VersionDetailOut,
    VersionOut,
)

router = APIRouter(prefix="/api", tags=["surveys"], dependencies=[Depends(current_user)])


# --------------------------------------------------------------------------- shaping the replies


def _survey_out(survey: Survey, completed: int = 0) -> dict:
    current = service.current_version(survey)
    return dict(
        id=survey.id, slug=survey.slug, title=survey.title, status=survey.status, target=survey.target,
        deadline=survey.deadline, live_at=survey.live_at, closed_at=survey.closed_at,
        closed_reason=survey.closed_reason, created_at=survey.created_at,
        current_version_no=current.version_no if current else None,
        has_draft=service.draft_of(survey) is not None,
        completed=completed or 0,
    )


def _version_out(version: SurveyVersion) -> dict:
    return dict(
        id=version.id, version_no=version.version_no, file_name=version.file_name, approved_at=version.approved_at,
        approved_by=version.approved_by.name if version.approved_by else None, question_count=len(version.questions),
    )


def _detail(db: Session, survey: Survey) -> SurveyDetailOut:
    draft = service.draft_of(survey)
    draft_out = None
    if draft is not None:
        draft_out = DraftOut(
            id=draft.id, file_name=draft.file_name, text=draft.file_text, updated_at=draft.updated_at,
            updated_by=draft.created_by.name if draft.created_by else None,
            check=CheckOut.of(service.check_text(draft.file_text, expected_slug=survey.slug)),
        )
    return SurveyDetailOut(
        **_survey_out(survey, respond_service.completes(db, survey.id)),
        versions=[VersionOut(**_version_out(v)) for v in reversed(service.approved_versions(survey))],
        draft=draft_out,
    )


def _read_upload(file: UploadFile) -> str:
    name = file.filename or "upload.txt"
    if not name.lower().endswith(".txt"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Please upload the questionnaire as a .txt file.")
    data = file.file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            f"The file is too big (limit {settings.max_upload_bytes // 1024} KB).")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The file is not plain UTF-8 text.") from None


# --------------------------------------------------------------------------- check only


@router.post("/check", response_model=CheckOut)
def check(body: TextIn):
    """Check text without saving it (used live by the editor)."""
    return CheckOut.of(service.check_text(body.text))


# --------------------------------------------------------------------------- surveys and drafts


@router.get("/surveys", response_model=list[SurveyOut])
def list_surveys(db: Session = Depends(get_db)):
    counts = reports.completed_counts(db)
    return [_survey_out(s, counts.get(s.id, 0)) for s in service.list_surveys(db)]


@router.post("/surveys", response_model=SurveyDetailOut, status_code=status.HTTP_201_CREATED)
def save_new_draft(body: TextIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Save pasted text as a draft. Same <survey id> as an existing survey -> its new draft."""
    survey, _ = service.save_draft(db, body.text, user, body.file_name)
    return _detail(db, survey)


@router.post("/surveys/upload", response_model=SurveyDetailOut, status_code=status.HTTP_201_CREATED)
def upload_draft(file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(current_user)):
    survey, _ = service.save_draft(db, _read_upload(file), user, file.filename)
    return _detail(db, survey)


@router.get("/surveys/{survey_id}", response_model=SurveyDetailOut)
def get_survey(survey_id: int, db: Session = Depends(get_db)):
    return _detail(db, service.refresh_status(db, service.get_survey(db, survey_id)))


@router.put("/surveys/{survey_id}/draft", response_model=SurveyDetailOut)
def update_draft(survey_id: int, body: TextIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    survey = service.get_survey(db, survey_id)
    service.save_draft(db, body.text, user, body.file_name, survey=survey)
    return _detail(db, survey)


@router.delete("/surveys/{survey_id}/draft", status_code=status.HTTP_204_NO_CONTENT)
def discard_draft(survey_id: int, db: Session = Depends(get_db)):
    service.discard_draft(db, service.get_survey(db, survey_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/surveys/{survey_id}/test-runs", response_model=TestRunOut, status_code=status.HTTP_201_CREATED)
def start_test_run(survey_id: int, body: TestRunIn | None = None, db: Session = Depends(get_db)):
    """Preview / test mode. Answers are flagged as test and never counted.
    Uses the draft if there is one, otherwise the current version (or say which with use_draft)."""
    survey = service.get_survey(db, survey_id)
    return respond_service.start_test_run(db, survey, body.use_draft if body else None)


@router.get("/surveys/{survey_id}/versions/{version_no}", response_model=VersionDetailOut)
def get_version(survey_id: int, version_no: int, db: Session = Depends(get_db)):
    version = service.get_version(service.get_survey(db, survey_id), version_no)
    return VersionDetailOut(
        **_version_out(version),
        text=version.file_text,
        questions=[QuestionOut.model_validate(q) for q in version.questions],
        quotas=[QuotaOut.model_validate(q) for q in version.quotas],
    )


# --------------------------------------------------------------------------- dashboard and export


@router.get("/surveys/{survey_id}/dashboard")
def dashboard(survey_id: int, db: Session = Depends(get_db)):
    """Live numbers: counts, quota groups, termination reasons, where people stopped."""
    return reports.dashboard(db, service.get_survey(db, survey_id))


@router.get("/surveys/{survey_id}/export")
def export(survey_id: int, format: Literal["csv", "xlsx"] = Query("csv"), db: Session = Depends(get_db)):
    """Completed responses in the standard format, as CSV or Excel."""
    survey = service.get_survey(db, survey_id)
    headers, rows = reports.export_table(db, survey)
    if format == "xlsx":
        content = reports.to_xlsx(headers, rows, survey.title)
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        content, media = reports.to_csv(headers, rows), "text/csv; charset=utf-8"
    name = reports.export_file_name(survey, format)
    return Response(content, media_type=media, headers={"Content-Disposition": f'attachment; filename="{name}"'})


# --------------------------------------------------------------------------- admin only


@router.post("/surveys/{survey_id}/approve", response_model=SurveyDetailOut)
def approve(survey_id: int, db: Session = Depends(get_db), user: User = Depends(admin_user)):
    survey = service.get_survey(db, survey_id)
    service.approve(db, survey, user)
    return _detail(db, survey)


@router.post("/surveys/{survey_id}/go-live", response_model=SurveyDetailOut, dependencies=[Depends(admin_user)])
def go_live(survey_id: int, body: GoLiveIn | None = None, db: Session = Depends(get_db)):
    survey = service.get_survey(db, survey_id)
    service.go_live(db, survey, body.deadline if body else None)
    return _detail(db, survey)


@router.patch("/surveys/{survey_id}/deadline", response_model=SurveyDetailOut, dependencies=[Depends(admin_user)])
def set_deadline(survey_id: int, body: DeadlineIn, db: Session = Depends(get_db)):
    survey = service.get_survey(db, survey_id)
    service.set_deadline(db, survey, body.deadline)
    return _detail(db, survey)


@router.post("/surveys/{survey_id}/close", response_model=SurveyDetailOut, dependencies=[Depends(admin_user)])
def close(survey_id: int, db: Session = Depends(get_db)):
    survey = service.get_survey(db, survey_id)
    service.close(db, survey)
    return _detail(db, survey)
