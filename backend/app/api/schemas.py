"""Shapes of the JSON going in and out of the API (validated by Pydantic)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.questionnaire import Issue, ParseResult

MAX_TEXT = 500_000  # characters; a real questionnaire is a few KB


# --------------------------------------------------------------------------- auth / users


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=200)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    name: str
    role: str
    is_active: bool


class LoginOut(BaseModel):
    token: str
    user: UserOut


class UserCreateIn(BaseModel):
    email: str = Field(min_length=3, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    name: str = Field(min_length=1, max_length=120)
    role: Literal["admin", "researcher"]
    password: str = Field(min_length=8, max_length=200)


# --------------------------------------------------------------------------- checking files


class IssueOut(BaseModel):
    line: int
    severity: str
    code: str
    message: str

    @classmethod
    def of(cls, issue: Issue) -> "IssueOut":
        return cls(line=issue.line, severity=issue.severity, code=issue.code, message=issue.message)


class SurveySummary(BaseModel):
    id: str | None
    title: str | None
    target: str | None
    questions: int
    quotas: int


class CheckOut(BaseModel):
    ok: bool
    error_count: int
    warning_count: int
    issues: list[IssueOut]
    survey: SurveySummary | None

    @classmethod
    def of(cls, result: ParseResult) -> "CheckOut":
        s = result.survey
        summary = None
        if s is not None:
            summary = SurveySummary(id=s.sid, title=s.title, target=s.target, questions=len(s.questions), quotas=len(s.quotas))
        return cls(
            ok=result.ok,
            error_count=len(result.errors),
            warning_count=len(result.warnings),
            issues=[IssueOut.of(i) for i in result.issues],
            survey=summary,
        )


class TextIn(BaseModel):
    text: str = Field(max_length=MAX_TEXT)
    file_name: str | None = Field(default=None, max_length=255)


# --------------------------------------------------------------------------- surveys


class VersionOut(BaseModel):
    id: int
    version_no: int
    file_name: str | None
    approved_at: datetime | None
    approved_by: str | None
    question_count: int


class DraftOut(BaseModel):
    id: int
    file_name: str | None
    text: str
    updated_at: datetime
    updated_by: str | None
    check: CheckOut


class SurveyOut(BaseModel):
    id: int
    slug: str
    title: str
    status: str
    target: int | None
    deadline: datetime | None
    live_at: datetime | None
    closed_at: datetime | None
    closed_reason: str | None
    created_at: datetime
    current_version_no: int | None
    has_draft: bool


class SurveyDetailOut(SurveyOut):
    versions: list[VersionOut]
    draft: DraftOut | None


class DeadlineIn(BaseModel):
    deadline: datetime


class GoLiveIn(BaseModel):
    deadline: datetime | None = None


class TestRunIn(BaseModel):
    use_draft: bool | None = None  # None = the draft if there is one, else the current version


class TestRunOut(BaseModel):
    token: str
    version_no: int | None
    is_draft: bool


class QuestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    qid: str
    type: str
    text: str
    required: bool
    options: list[dict[str, Any]]
    rows: list[str]
    rules: dict[str, Any]
    line: int | None


class QuotaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    question_qid: str
    value: str
    target: int


class VersionDetailOut(VersionOut):
    text: str
    questions: list[QuestionOut]
    quotas: list[QuotaOut]
