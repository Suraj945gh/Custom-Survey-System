"""Read a questionnaire .txt file into SurveyDef objects.

Why not a normal XML parser? The files are not valid XML: they use bare attributes
(`required`), apostrophes and `<` signs in plain text. A strict parser would stop at
the first problem. This reader is tolerant: it keeps going, records every structure
problem as an Issue with a line number, and never raises on bad input.

It works in two passes:
1. `_scan`  turns the text into tokens: opening tags, closing tags and plain text.
2. `_build` walks the tokens with a stack and fills in the SurveyDef tree.

Checking the *content* (unknown types, broken references...) is the validator's job.
"""

from __future__ import annotations

import bisect
import difflib
import html
import re
from dataclasses import dataclass, field

from .models import Attrs, Issue, OptionDef, ParseResult, QuestionDef, QuotaDef, RowDef, SurveyDef

# Which tag may sit directly inside which. "root" means top level of the file.
ALLOWED_PARENTS: dict[str, set[str]] = {
    "survey": {"root"},
    "question": {"survey"},
    "quota": {"survey"},
    "text": {"question"},
    "option": {"question"},
    "row": {"question"},
}
KNOWN_TAGS = list(ALLOWED_PARENTS)
TEXT_HOLDERS = {"text", "option", "row"}  # tags whose content is plain text

TAG_START = re.compile(r"<(/?)([A-Za-z][\w-]*)")
ATTR = re.compile(r"""([A-Za-z_][\w:.-]*)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+)))?""")


# --------------------------------------------------------------------------- tokens


@dataclass
class _Tag:
    name: str
    closing: bool
    self_closing: bool
    pos: int
    attrs: Attrs = field(default_factory=Attrs)


@dataclass
class _Text:
    value: str
    pos: int


class _Lines:
    """Turns a character position into a 1-based line number."""

    def __init__(self, text: str):
        self._starts = [0] + [i + 1 for i, c in enumerate(text) if c == "\n"]

    def __call__(self, pos: int) -> int:
        return bisect.bisect_right(self._starts, pos)


def _clean(value: str) -> str:
    """Decode &amp; style entities and collapse runs of whitespace."""
    return " ".join(html.unescape(value).split())


# --------------------------------------------------------------------------- pass 1: scan


def _scan(text: str, line_of: _Lines, issues: list[Issue]) -> list[_Tag | _Text]:
    tokens: list[_Tag | _Text] = []
    n = len(text)
    i = 0
    while i < n:
        lt = text.find("<", i)
        if lt == -1:
            tokens.append(_Text(text[i:], i))
            break
        if lt > i:
            tokens.append(_Text(text[i:lt], i))

        # Comments: <!-- ... -->
        if text.startswith("<!--", lt):
            end = text.find("-->", lt + 4)
            if end == -1:
                issues.append(Issue(line_of(lt), "A comment '<!--' is never closed with '-->'.", "broken_comment"))
                break
            i = end + 3
            continue

        m = TAG_START.match(text, lt)
        if not m:
            # A lone '<' in normal text, e.g. "age < 18".
            tokens.append(_Text("<", lt))
            i = lt + 1
            continue

        closing, name = m.group(1) == "/", m.group(2).lower()
        end, quote = m.end(), None
        while end < n:
            c = text[end]
            if quote:
                if c == quote:
                    quote = None
                elif c == "\n":
                    issues.append(Issue(line_of(end), f"A quote in the <{name}> tag is not closed.", "quote_not_closed"))
                    quote = None
            elif c in "\"'":
                quote = c
            elif c in "<>":
                break
            end += 1

        if end >= n or text[end] != ">":
            issues.append(Issue(line_of(lt), f"The <{name}> tag is not closed with '>'.", "broken_tag"))
            i = end
            continue

        inner = text[m.end():end]
        self_closing = inner.rstrip().endswith("/")
        if self_closing:
            inner = inner.rstrip()[:-1]
        tag = _Tag(name, closing, self_closing, lt)
        if not closing:
            tag.attrs = _read_attrs(name, inner, m.end(), line_of, issues)
        tokens.append(tag)
        i = end + 1
    return tokens


def _read_attrs(tag: str, inner: str, offset: int, line_of: _Lines, issues: list[Issue]) -> Attrs:
    attrs = Attrs()
    pos = 0
    while pos < len(inner):
        if inner[pos].isspace():
            pos += 1
            continue
        m = ATTR.match(inner, pos)
        if not m:
            # Junk such as a stray quote or '='. Report the whole run once.
            junk_end = pos
            while junk_end < len(inner) and not inner[junk_end].isspace():
                junk_end += 1
            issues.append(
                Issue(
                    line_of(offset + pos),
                    f"Could not read '{inner[pos:junk_end]}' in the <{tag}> tag.",
                    "broken_attribute",
                )
            )
            pos = junk_end
            continue
        key = m.group(1).lower()
        raw = next((g for g in m.group(2, 3, 4) if g is not None), "")
        line = line_of(offset + pos)
        if key in attrs.values:
            issues.append(Issue(line, f"The <{tag}> tag has '{key}' twice.", "duplicate_attribute"))
        else:
            attrs.values[key] = html.unescape(raw).strip()
            attrs.lines[key] = line
        pos = m.end()
    return attrs


# --------------------------------------------------------------------------- pass 2: build


@dataclass
class _Open:
    """An element that is currently open on the stack."""

    kind: str  # tag name, or "ignored" for unknown / misplaced tags
    name: str
    line: int
    obj: object = None
    parts: list[str] = field(default_factory=list)


def _build(tokens: list[_Tag | _Text], line_of: _Lines, issues: list[Issue]) -> SurveyDef | None:
    survey: SurveyDef | None = None
    survey_done = False
    stack: list[_Open] = []

    def top_kind() -> str:
        return stack[-1].kind if stack else "root"

    def finish(el: _Open) -> None:
        """Called whenever an element ends, normally or because it was never closed."""
        if el.kind not in TEXT_HOLDERS:
            return
        value = _clean("".join(el.parts))
        if el.kind == "text":
            question: QuestionDef = el.obj
            question.text, question.text_line = value, el.line
        else:
            el.obj.label = value

    def close_unclosed(el: _Open) -> None:
        issues.append(Issue(el.line, f"<{el.name}> on line {el.line} is not closed (missing </{el.name}>).", "unclosed_tag"))
        finish(el)

    for tok in tokens:
        if isinstance(tok, _Text):
            if top_kind() in TEXT_HOLDERS:
                stack[-1].parts.append(tok.value)
            elif top_kind() != "ignored" and tok.value.strip():
                first = tok.pos + (len(tok.value) - len(tok.value.lstrip()))
                where = "a <text>, <option> or <row>" if top_kind() == "question" else "any tag"
                issues.append(
                    Issue(
                        line_of(first),
                        f"Unexpected text '{_clean(tok.value)[:40]}' outside {where}.",
                        "stray_text",
                    )
                )
            continue

        line = line_of(tok.pos)

        # ---- closing tag
        if tok.closing:
            names = [el.name for el in stack]
            if tok.name not in names:
                issues.append(Issue(line, f"</{tok.name}> has no matching opening tag.", "stray_closing_tag"))
                continue
            while stack[-1].name != tok.name:
                close_unclosed(stack.pop())
            el = stack.pop()
            finish(el)
            if el.kind == "survey":
                survey_done = True
            continue

        # ---- opening tag
        if top_kind() == "ignored":
            if not tok.self_closing:
                stack.append(_Open("ignored", tok.name, line))
            continue

        if tok.name not in ALLOWED_PARENTS:
            hint = difflib.get_close_matches(tok.name, KNOWN_TAGS, n=1, cutoff=0.6)
            extra = f" Did you mean <{hint[0]}>?" if hint else ""
            issues.append(Issue(line, f"Unknown tag <{tok.name}>.{extra}", "unknown_tag"))
            if not tok.self_closing:
                stack.append(_Open("ignored", tok.name, line))
            continue

        allowed = ALLOWED_PARENTS[tok.name]
        if tok.name == "survey" and (survey is not None):
            issues.append(Issue(line, "Only one <survey> is allowed per file.", "second_survey"))
            if not tok.self_closing:
                stack.append(_Open("ignored", tok.name, line))
            continue

        if top_kind() not in allowed:
            # Maybe an earlier tag was simply not closed, e.g. a missing </question>.
            depth = next((d for d in range(len(stack) - 1, -1, -1) if stack[d].kind in allowed), None)
            if depth is not None:
                while len(stack) > depth + 1:
                    close_unclosed(stack.pop())
            else:
                parent = " or ".join(f"<{p}>" for p in sorted(allowed))
                where = "after </survey>" if survey_done else f"here; it belongs inside {parent}"
                issues.append(Issue(line, f"<{tok.name}> cannot be {where}.", "misplaced_tag"))
                if not tok.self_closing:
                    stack.append(_Open("ignored", tok.name, line))
                continue

        el = _Open(tok.name, tok.name, line)
        if tok.name == "survey":
            survey = SurveyDef(line=line, attrs=tok.attrs)
            el.obj = survey
        elif tok.name == "question":
            el.obj = QuestionDef(line=line, attrs=tok.attrs)
            survey.questions.append(el.obj)
        elif tok.name == "quota":
            el.obj = QuotaDef(line=line, attrs=tok.attrs)
            survey.quotas.append(el.obj)
        elif tok.name == "option":
            el.obj = OptionDef(label="", line=line, attrs=tok.attrs)
            stack[-1].obj.options.append(el.obj)
        elif tok.name == "row":
            el.obj = RowDef(label="", line=line)
            stack[-1].obj.rows.append(el.obj)
        elif tok.name == "text":
            question: QuestionDef = stack[-1].obj
            if question.text_line is not None:
                issues.append(Issue(line, f"This question already has a <text> (line {question.text_line}).", "duplicate_text"))
                el = _Open("ignored", tok.name, line)
            else:
                el.obj = question

        if tok.self_closing:
            finish(el)
        else:
            stack.append(el)

    while stack:
        el = stack.pop()
        if el.kind == "ignored":
            issues.append(Issue(el.line, f"<{el.name}> on line {el.line} is not closed (missing </{el.name}>).", "unclosed_tag"))
        else:
            close_unclosed(el)
    return survey


# --------------------------------------------------------------------------- public


def parse_questionnaire(text: str) -> ParseResult:
    """Parse questionnaire text. Never raises; problems come back as Issues."""
    text = (text or "").lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n")
    issues: list[Issue] = []
    if not text.strip():
        return ParseResult(None, [Issue(1, "The file is empty.", "empty_file")])

    line_of = _Lines(text)
    tokens = _scan(text, line_of, issues)
    survey = _build(tokens, line_of, issues)
    if survey is None:
        issues.append(Issue(1, "No <survey> tag found. The file must start with <survey ...>.", "no_survey"))
    issues.sort(key=lambda i: i.line)
    return ParseResult(survey, issues)
