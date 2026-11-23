"""One answer: is it valid, how is it shown, does it match a value?

How answers are stored (the `value` of an Answer row, as JSON):
    single / dropdown / yesno / consent   "Samsung"                  (the option label)
    multi                                 ["Samsung", "Other (specify)"]
    rating / nps                          4
    number                                25000
    text / longtext / formatted           "Ravi"
    matrix                                {"The battery lasts a full day": "Agree", ...}
    info, or an optional question left empty: null
The text typed into an "Other (specify)" box is kept separately as `other_text`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

CHOICE = {"single", "dropdown", "yesno", "consent"}
NUMERIC = {"rating", "nps", "number"}

TEXT_LIMITS = {"text": 500, "longtext": 5000, "formatted": 200}
OTHER_TEXT_LIMIT = 300

PINCODE = re.compile(r"^[1-9]\d{5}$")
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")


class AnswerError(ValueError):
    """The answer can't be accepted. The message is shown to the respondent."""


@dataclass(frozen=True)
class Given:
    """An answer as saved: the value plus the typed 'Other' text (if any)."""

    value: Any
    other_text: str | None = None


@dataclass(frozen=True)
class Option:
    """An option as shown to one respondent (options-from can create options from typed text)."""

    value: str
    label: str
    fixed: bool = False
    other: bool = False
    exclusive: bool = False
    skip_to: str | None = None


@dataclass
class Settings:
    """Numbers a question uses for checking, with the defaults filled in."""

    min: float | None = None
    max: float | None = None
    minlength: int | None = None
    maxlength: int | None = None
    format: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


def norm(value: Any) -> str:
    return " ".join(str(value).split()).casefold()


def as_number(value: Any) -> float | None:
    if isinstance(value, bool):  # True is an int in Python; never a valid number answer
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    elif isinstance(value, str) and value.strip():
        try:
            number = float(value.strip().replace(",", ""))
        except ValueError:
            return None
    else:
        return None
    return number if number == number and abs(number) != float("inf") else None


def show_number(number: float) -> int | float:
    return int(number) if float(number).is_integer() else number


def normalise_phone(raw: Any) -> str | None:
    """Indian mobile number -> 10 digits, or None. Accepts +91, 91, 0 and spaces / dashes."""
    if not isinstance(raw, str):
        return None
    digits = re.sub(r"[\s\-().]", "", raw)
    if digits.startswith("+91"):
        digits = digits[3:]
    elif len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    return digits if re.fullmatch(r"[6-9]\d{9}", digits) else None


def settings_of(question) -> Settings:
    rules, kind = question.rules or {}, question.type
    s = Settings(
        min=rules.get("min"), max=rules.get("max"),
        minlength=rules.get("minlength"), maxlength=rules.get("maxlength"), format=rules.get("format"),
    )
    if kind == "rating":
        s.min = 1 if s.min is None else s.min
        s.max = 5 if s.max is None else s.max
    elif kind == "nps":
        s.min, s.max = 0, 10
    if kind in TEXT_LIMITS:
        s.maxlength = min(s.maxlength, TEXT_LIMITS[kind]) if s.maxlength else TEXT_LIMITS[kind]
    return s


# --------------------------------------------------------------------------- checking an answer


def clean_answer(question, value: Any, other_text: Any, options: list[Option]) -> Given:
    """Check a submitted answer and return it in its stored form. Raises AnswerError."""
    kind = question.type
    if kind == "info":
        return Given(None)
    if _is_empty(value):
        if question.required:
            raise AnswerError("Please answer this question.")
        return Given(None)

    if kind in CHOICE:
        return _clean_single(value, other_text, options)
    if kind == "multi":
        return _clean_multi(question, value, other_text, options)
    if kind in NUMERIC:
        return Given(_clean_number(question, value))
    if kind in ("text", "longtext"):
        return Given(_clean_text(question, value))
    if kind == "formatted":
        return Given(_clean_formatted(question, value))
    if kind == "matrix":
        return Given(_clean_matrix(question, value, options))
    raise AnswerError("This question type is not supported.")


def _is_empty(value: Any) -> bool:
    return value is None or (isinstance(value, (str, list, dict)) and not (value.strip() if isinstance(value, str) else value))


def _find(options: list[Option], value: Any) -> Option:
    if isinstance(value, str):
        for option in options:
            if option.value == value or norm(option.value) == norm(value):
                return option
    raise AnswerError("Please choose one of the options shown.")


def _clean_other(option: Option, other_text: Any) -> str | None:
    if not option.other:
        return None
    text = " ".join(other_text.split()) if isinstance(other_text, str) else ""
    if not text:
        raise AnswerError(f"Please type your answer for '{option.label}'.")
    if len(text) > OTHER_TEXT_LIMIT:
        raise AnswerError(f"Please keep it under {OTHER_TEXT_LIMIT} characters.")
    return text


def _clean_single(value: Any, other_text: Any, options: list[Option]) -> Given:
    option = _find(options, value)
    return Given(option.value, _clean_other(option, other_text))


def _clean_multi(question, value: Any, other_text: Any, options: list[Option]) -> Given:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        raise AnswerError("Please choose from the options shown.")
    chosen: list[Option] = []
    for item in value:
        option = _find(options, item)
        if option not in chosen:
            chosen.append(option)
    exclusive = [o for o in chosen if o.exclusive]
    if exclusive and len(chosen) > 1:
        raise AnswerError(f"'{exclusive[0].label}' can't be combined with other options.")
    s = settings_of(question)
    if s.max is not None and len(chosen) > s.max:
        raise AnswerError(f"Please choose at most {show_number(s.max)}.")
    if s.min is not None and len(chosen) < s.min:
        raise AnswerError(f"Please choose at least {show_number(s.min)}.")
    other = next((o for o in chosen if o.other), None)
    # Keep the order the options were defined in, so exports and piping are stable.
    ordered = [o.value for o in options if o in chosen]
    return Given(ordered, _clean_other(other, other_text) if other else None)


def _clean_number(question, value: Any) -> int | float:
    number = as_number(value)
    if number is None:
        raise AnswerError("Please enter a number.")
    s = settings_of(question)
    if question.type in ("rating", "nps") and not number.is_integer():
        raise AnswerError("Please choose one of the points on the scale.")
    if s.min is not None and number < s.min or s.max is not None and number > s.max:
        if s.min is not None and s.max is not None:
            raise AnswerError(f"Please enter a number from {show_number(s.min)} to {show_number(s.max)}.")
        if s.min is not None:
            raise AnswerError(f"Please enter {show_number(s.min)} or more.")
        raise AnswerError(f"Please enter {show_number(s.max)} or less.")
    return show_number(number)


def _clean_text(question, value: Any) -> str:
    if not isinstance(value, str):
        raise AnswerError("Please type your answer.")
    text = value.strip() if question.type == "longtext" else " ".join(value.split())
    s = settings_of(question)
    if s.minlength and len(text) < s.minlength:
        raise AnswerError(f"Please write at least {s.minlength} characters ({len(text)} so far).")
    if s.maxlength and len(text) > s.maxlength:
        raise AnswerError(f"Please keep it under {s.maxlength} characters.")
    return text


def _clean_formatted(question, value: Any) -> str:
    if not isinstance(value, str):
        raise AnswerError("Please type your answer.")
    fmt = settings_of(question).format
    text = value.strip()
    if fmt == "pincode":
        text = text.replace(" ", "")
        if not PINCODE.match(text):
            raise AnswerError("Please enter a valid 6-digit pincode.")
        return text
    if fmt == "phone":
        phone = normalise_phone(text)
        if phone is None:
            raise AnswerError("Please enter a valid 10-digit mobile number.")
        return phone
    if fmt == "email":
        if not EMAIL.match(text) or len(text) > 254:
            raise AnswerError("Please enter a valid email address.")
        return text
    return text


def _clean_matrix(question, value: Any, options: list[Option]) -> dict[str, str]:
    if not isinstance(value, dict):
        raise AnswerError("Please answer each row.")
    rows = list(question.rows or [])
    clean: dict[str, str] = {}
    for row in rows:
        picked = value.get(row)
        if picked in (None, ""):
            continue
        clean[row] = _find(options, picked).value
    unknown = [key for key in value if key not in rows]
    if unknown:
        raise AnswerError("Please answer the rows shown.")
    if question.required and len(clean) < len(rows):
        missing = len(rows) - len(clean)
        raise AnswerError(f"Please answer every row ({missing} left).")
    if not clean and not question.required:
        return {}
    return clean


# --------------------------------------------------------------------------- showing and matching


def display(question, given: Given | None) -> str:
    """An answer as text: used for piping [qN] (and later the export).
    A picked 'Other (specify)' shows what the person typed."""
    if given is None or given.value is None:
        return ""
    value = given.value
    other_labels = {o["label"] for o in (question.options or []) if o.get("other")}
    if isinstance(value, list):
        return ", ".join(given.other_text if item in other_labels and given.other_text else str(item) for item in value)
    if isinstance(value, dict):
        return "; ".join(f"{row}: {answer}" for row, answer in value.items())
    if isinstance(value, str) and value in other_labels and given.other_text:
        return given.other_text
    if isinstance(value, float):
        return str(show_number(value))
    return str(value)


def matches(value: Any, other_text: str | None, wanted: str) -> bool:
    """Does a stored answer equal `wanted`? (terminate-on, quotas and show-if '=')
    A list (multi) matches if `wanted` was one of the picks."""
    if value is None:
        return False
    if isinstance(value, list):
        return any(norm(item) == norm(wanted) for item in value) or (
            other_text is not None and norm(other_text) == norm(wanted)
        )
    if isinstance(value, dict):
        return False
    number, target = as_number(value), as_number(wanted)
    if number is not None and target is not None:
        return number == target
    return norm(value) == norm(wanted) or (other_text is not None and norm(other_text) == norm(wanted))
