"""Public routes for respondents (no login). The token in the link is their key."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.services import respond as service

router = APIRouter(prefix="/api/public", tags=["respondent"])


class PublicSurveyOut(BaseModel):
    slug: str
    title: str
    open: bool
    message: str | None


class JoinIn(BaseModel):
    phone: str = Field(min_length=1, max_length=20)


class JoinOut(BaseModel):
    token: str
    resumed: bool


class AnswerIn(BaseModel):
    qid: str = Field(min_length=1, max_length=100)
    value: Any = None
    other_text: str | None = Field(default=None, max_length=1000)


class ScreenOut(BaseModel):
    """Either a question to show (kind="question") or an end screen (kind="end")."""

    kind: Literal["question", "end"]
    survey_title: str
    is_test: bool
    progress: int | None = None
    # question screens
    previous_qid: str | None = None
    question: dict[str, Any] | None = None
    answer: dict[str, Any] | None = None
    # end screens: completed | already_completed | not_eligible | closed
    end: str | None = None
    title: str | None = None
    message: str | None = None
    reasons: str | None = None  # only for test runs


@router.get("/surveys/{slug}", response_model=PublicSurveyOut)
def survey_info(slug: str, db: Session = Depends(get_db)):
    return service.public_info(db, slug)


@router.post("/surveys/{slug}/join", response_model=JoinOut)
def join(slug: str, body: JoinIn, db: Session = Depends(get_db)):
    return service.join(db, slug, body.phone)


@router.get("/r/{token}", response_model=ScreenOut)
def current_screen(token: str, db: Session = Depends(get_db)):
    """Open (or reopen) a personal link: resumes at the next unanswered question."""
    return service.open_link(db, token)


@router.get("/r/{token}/questions/{qid}", response_model=ScreenOut)
def question_screen(token: str, qid: str, db: Session = Depends(get_db)):
    """Back: an earlier question with its saved answer."""
    return service.show_question(db, token, qid)


@router.post("/r/{token}/answers", response_model=ScreenOut)
def answer(token: str, body: AnswerIn, db: Session = Depends(get_db)):
    """Save one answer (at once) and get the next screen."""
    return service.submit(db, token, body.qid, body.value, body.other_text)
