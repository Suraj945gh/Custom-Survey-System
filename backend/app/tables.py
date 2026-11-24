"""The 8 database tables from design/database.md.

The build adds a few practical columns the diagram left out (timestamps, who did what,
the survey's slug, question order). They are listed in docs/database_build_notes.md.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base, UTCDateTime, utcnow

# ---- allowed values (kept as plain strings in the database)
ROLE_ADMIN, ROLE_RESEARCHER = "admin", "researcher"
ROLES = (ROLE_ADMIN, ROLE_RESEARCHER)

SURVEY_DRAFT, SURVEY_LIVE, SURVEY_CLOSED = "draft", "live", "closed"
CLOSED_BY_TEAM, CLOSED_DEADLINE, CLOSED_TARGET = "closed_by_team", "deadline_passed", "target_reached"

RESPONSE_IN_PROGRESS, RESPONSE_COMPLETED, RESPONSE_TERMINATED = "in_progress", "completed", "terminated"


class User(Base):
    """A staff member: admin or researcher. Respondents never log in."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(20))
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Survey(Base):
    """One study. Holds its status and deadline; the questions live in its versions."""

    __tablename__ = "surveys"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)  # <survey id="..."> in the file
    title: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default=SURVEY_DRAFT)
    target: Mapped[int | None] = mapped_column(Integer)
    deadline: Mapped[datetime | None] = mapped_column(UTCDateTime)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    live_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    closed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    closed_reason: Mapped[str | None] = mapped_column(String(30))

    created_by: Mapped[User | None] = relationship()
    versions: Mapped[list[SurveyVersion]] = relationship(
        back_populates="survey", cascade="all, delete-orphan", order_by="SurveyVersion.id"
    )


class SurveyVersion(Base):
    """One uploaded file. version_no stays empty while it is a draft and is set on approval.
    After approval the row (and its questions) never change."""

    __tablename__ = "survey_versions"
    __table_args__ = (UniqueConstraint("survey_id", "version_no"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    survey_id: Mapped[int] = mapped_column(ForeignKey("surveys.id", ondelete="CASCADE"), index=True)
    version_no: Mapped[int | None] = mapped_column(Integer)
    file_name: Mapped[str | None] = mapped_column(String(255))
    file_text: Mapped[str] = mapped_column(Text)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)
    approved_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    survey: Mapped[Survey] = relationship(back_populates="versions")
    created_by: Mapped[User | None] = relationship(foreign_keys=[created_by_id])
    approved_by: Mapped[User | None] = relationship(foreign_keys=[approved_by_id])
    questions: Mapped[list[Question]] = relationship(
        back_populates="version", cascade="all, delete-orphan", order_by="Question.position"
    )
    quotas: Mapped[list[Quota]] = relationship(back_populates="version", cascade="all, delete-orphan", order_by="Quota.id")

    @property
    def is_draft(self) -> bool:
        return self.version_no is None


class Question(Base):
    """One question of one version. Options and rules are JSON so any survey fits the same table."""

    __tablename__ = "questions"
    __table_args__ = (UniqueConstraint("version_id", "qid"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    version_id: Mapped[int] = mapped_column(ForeignKey("survey_versions.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)  # 0, 1, 2... order in the file
    qid: Mapped[str] = mapped_column(String(100))
    type: Mapped[str] = mapped_column(String(20))
    text: Mapped[str] = mapped_column(Text)
    required: Mapped[bool] = mapped_column(Boolean, default=False)
    options: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    rows: Mapped[list[str]] = mapped_column(JSON, default=list)
    rules: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    line: Mapped[int | None] = mapped_column(Integer)  # line in the uploaded file

    version: Mapped[SurveyVersion] = relationship(back_populates="questions")


class Quota(Base):
    __tablename__ = "quotas"

    id: Mapped[int] = mapped_column(primary_key=True)
    version_id: Mapped[int] = mapped_column(ForeignKey("survey_versions.id", ondelete="CASCADE"), index=True)
    question_qid: Mapped[str] = mapped_column(String(100))
    value: Mapped[str] = mapped_column(String(255))
    target: Mapped[int] = mapped_column(Integer)

    version: Mapped[SurveyVersion] = relationship(back_populates="quotas")


class Respondent(Base):
    """One person, known only by phone number (for the 3-month rule and one link per person)."""

    __tablename__ = "respondents"

    id: Mapped[int] = mapped_column(primary_key=True)
    phone: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Response(Base):
    """One person's attempt at one survey, pinned to the version it started on."""

    __tablename__ = "responses"
    __table_args__ = (UniqueConstraint("survey_id", "respondent_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    survey_id: Mapped[int] = mapped_column(ForeignKey("surveys.id", ondelete="CASCADE"), index=True)
    version_id: Mapped[int] = mapped_column(ForeignKey("survey_versions.id", ondelete="CASCADE"), index=True)
    respondent_id: Mapped[int | None] = mapped_column(ForeignKey("respondents.id"))  # empty for test runs
    status: Mapped[str] = mapped_column(String(20), default=RESPONSE_IN_PROGRESS)
    end_reasons: Mapped[str | None] = mapped_column(Text)  # "q4: City not in scope | q3: Quota full (Male)"
    silent_end: Mapped[bool] = mapped_column(Boolean, default=False)  # screened out without being told
    is_test: Mapped[bool] = mapped_column(Boolean, default=False)
    option_orders: Mapped[dict[str, list[str]]] = mapped_column(JSON, default=dict)  # saved shuffle order
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    survey: Mapped[Survey] = relationship()
    version: Mapped[SurveyVersion] = relationship()
    respondent: Mapped[Respondent | None] = relationship()
    answers: Mapped[list[Answer]] = relationship(back_populates="response", cascade="all, delete-orphan")


class Answer(Base):
    """One answer, saved the moment it is given. One row per (response, question)."""

    __tablename__ = "answers"
    __table_args__ = (UniqueConstraint("response_id", "question_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    response_id: Mapped[int] = mapped_column(ForeignKey("responses.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), index=True)
    value: Mapped[Any] = mapped_column(JSON)
    other_text: Mapped[str | None] = mapped_column(String(500))
    answered_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)

    response: Mapped[Response] = relationship(back_populates="answers")
    question: Mapped[Question] = relationship()
