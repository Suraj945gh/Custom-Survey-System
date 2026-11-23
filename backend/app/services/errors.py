"""One error type for every rule a user can break. The API turns it into a JSON reply."""

from __future__ import annotations

from app.questionnaire import Issue


class ServiceError(Exception):
    def __init__(self, message: str, status: int = 400, issues: list[Issue] | None = None, extra: dict | None = None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.issues = issues or []
        self.extra = extra or {}  # more fields for the reply, e.g. {"code": "cool_off", "eligible_from": ...}


def not_found(what: str) -> ServiceError:
    return ServiceError(f"{what} not found.", 404)


def conflict(message: str, issues: list[Issue] | None = None) -> ServiceError:
    """The request is fine, but the current state does not allow it (e.g. approving a draft with errors)."""
    return ServiceError(message, 409, issues)
