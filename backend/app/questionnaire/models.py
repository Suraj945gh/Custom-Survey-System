"""Plain data shapes for a parsed questionnaire file.

The parser only fills these in. It does not judge whether the content makes sense
(unknown types, broken references...). That is the validator's job, so every
attribute is kept as the raw string from the file, together with its line number.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Severity = Literal["error", "warning"]

TRUE_WORDS = {"", "true", "yes", "1"}


def is_true(value: str | None) -> bool:
    """Bare attributes (`required`) and `"true"` / `"yes"` / `"1"` count as true."""
    return value is not None and value.strip().lower() in TRUE_WORDS


@dataclass
class Issue:
    """One problem found in the file, shown to the researcher."""

    line: int
    message: str
    code: str
    severity: Severity = "error"

    def __str__(self) -> str:
        return f"Line {self.line}: {self.message}"


@dataclass
class Attrs:
    """Attributes of one tag: raw values plus the line each one was written on."""

    values: dict[str, str] = field(default_factory=dict)
    lines: dict[str, int] = field(default_factory=dict)

    def get(self, name: str) -> str | None:
        return self.values.get(name)

    def has(self, name: str) -> bool:
        return name in self.values

    def flag(self, name: str) -> bool:
        return is_true(self.values.get(name))

    def line_of(self, name: str, default: int) -> int:
        return self.lines.get(name, default)


@dataclass
class OptionDef:
    label: str
    line: int
    attrs: Attrs = field(default_factory=Attrs)

    @property
    def fixed(self) -> bool:
        return self.attrs.flag("fixed")

    @property
    def is_other(self) -> bool:
        return self.attrs.flag("other")

    @property
    def exclusive(self) -> bool:
        return self.attrs.flag("exclusive")

    @property
    def skip_to(self) -> str | None:
        return self.attrs.get("skip-to")


@dataclass
class RowDef:
    label: str
    line: int


@dataclass
class QuestionDef:
    line: int
    attrs: Attrs = field(default_factory=Attrs)
    text: str = ""
    text_line: int | None = None
    options: list[OptionDef] = field(default_factory=list)
    rows: list[RowDef] = field(default_factory=list)

    @property
    def qid(self) -> str | None:
        return self.attrs.get("id")

    @property
    def type(self) -> str | None:
        return self.attrs.get("type")

    @property
    def required(self) -> bool:
        return self.attrs.flag("required")

    @property
    def shuffle(self) -> bool:
        return self.attrs.flag("shuffle")

    @property
    def silent(self) -> bool:
        return self.attrs.flag("silent")


@dataclass
class QuotaDef:
    line: int
    attrs: Attrs = field(default_factory=Attrs)

    @property
    def question(self) -> str | None:
        return self.attrs.get("question")

    @property
    def value(self) -> str | None:
        return self.attrs.get("value")

    @property
    def target(self) -> str | None:
        return self.attrs.get("target")


@dataclass
class SurveyDef:
    line: int
    attrs: Attrs = field(default_factory=Attrs)
    questions: list[QuestionDef] = field(default_factory=list)
    quotas: list[QuotaDef] = field(default_factory=list)

    @property
    def sid(self) -> str | None:
        return self.attrs.get("id")

    @property
    def title(self) -> str | None:
        return self.attrs.get("title")

    @property
    def target(self) -> str | None:
        return self.attrs.get("target")


@dataclass
class ParseResult:
    survey: SurveyDef | None
    issues: list[Issue] = field(default_factory=list)

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def ok(self) -> bool:
        return self.survey is not None and not self.errors
