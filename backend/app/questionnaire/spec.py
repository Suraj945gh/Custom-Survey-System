"""Turn a checked SurveyDef into plain, clean data ("the spec").

The parser keeps everything as raw text ("5", "true", "Single"). Once the validator
says there are no errors, this module converts it into the final form that is
stored in the database and used by the survey engine:

    numbers are numbers, flags are True/False, types are lower case,
    empty rules are left out.

Only call this on a survey without errors (the validator guarantees the values are sane).
"""

from __future__ import annotations

from typing import Any

from .models import QuestionDef, SurveyDef

# Attribute name in the file -> key in the stored rules, and how to convert it.
_RULES: dict[str, tuple[str, type]] = {
    "show-if": ("show_if", str),
    "terminate-on": ("terminate_on", str),
    "reason": ("reason", str),
    "options-from": ("options_from", str),
    "format": ("format", str),
    "low-label": ("low_label", str),
    "high-label": ("high_label", str),
    "min": ("min", float),
    "max": ("max", float),
    "minlength": ("minlength", int),
    "maxlength": ("maxlength", int),
}
_FLAGS = {"shuffle": "shuffle", "silent": "silent"}


def _number(value: str, kind: type) -> int | float | None:
    try:
        number = float(value)
    except ValueError:
        return None
    if kind is int or number.is_integer():
        return int(number)
    return number


def question_spec(q: QuestionDef) -> dict[str, Any]:
    rules: dict[str, Any] = {}
    for attr, (key, kind) in _RULES.items():
        raw = q.attrs.get(attr)
        if raw is None or raw == "":
            continue
        value = raw if kind is str else _number(raw, kind)
        if value is not None:
            rules[key] = value.lower() if key == "format" else value
    for attr, key in _FLAGS.items():
        if q.attrs.flag(attr):
            rules[key] = True

    return {
        "qid": q.qid,
        "type": (q.type or "").strip().lower(),
        "text": q.text,
        "required": q.required,
        "options": [
            {
                "label": o.label,
                "fixed": o.fixed,
                "other": o.is_other,
                "exclusive": o.exclusive,
                "skip_to": o.skip_to,
            }
            for o in q.options
        ],
        "rows": [r.label for r in q.rows],
        "rules": rules,
        "line": q.line,
    }


def survey_spec(survey: SurveyDef) -> dict[str, Any]:
    return {
        "id": survey.sid,
        "title": survey.title or survey.sid,
        "target": int(survey.target),
        "questions": [question_spec(q) for q in survey.questions],
        "quotas": [
            {"question": quota.question, "value": quota.value, "target": int(quota.target)}
            for quota in survey.quotas
        ],
    }
