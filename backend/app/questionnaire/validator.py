"""Check that a parsed questionnaire makes sense before it can be approved.

The parser (step 1) answers "can the file be read?". This module answers
"does what is written make sense?". It goes through the survey once and collects
every problem, so the researcher sees all of them together, each with a line number.

Two kinds of problems:
    error    must be fixed; the survey cannot be approved while one exists.
    warning  worth a look, but does not block approval (e.g. a quota larger than the target).

The checks, in the order they run:
    1. survey tag     id, title, target
    2. question ids   missing, badly written, used twice
    3. each question  type, text, options, type-specific rules (min/max, format, matrix...)
    4. each rule      show-if, terminate-on, skip-to, options-from, [qN] piping:
                      does the question it points to exist, and is it in the right place?
                      Is the value one that question can actually have?
    5. quotas         question and value exist, target is a number, targets add up
"""

from __future__ import annotations

import difflib
import re

from .conditions import ORDER_OPERATORS, ConditionError, comparisons, parse_condition
from .models import Attrs, Issue, ParseResult, QuestionDef, SurveyDef
from .parser import parse_questionnaire

QUESTION_TYPES = [
    "single", "multi", "dropdown", "yesno", "rating", "nps", "matrix",
    "text", "longtext", "number", "formatted", "info", "consent",
]
CHOICE_TYPES = {"single", "multi", "dropdown"}
OPTION_TYPES = CHOICE_TYPES | {"yesno", "consent", "matrix"}  # types that may have <option>
FORMATS = ["pincode", "phone", "email"]

SURVEY_ATTRS = {"id", "title", "target"}
QUESTION_ATTRS = {
    "id", "type", "required", "show-if", "terminate-on", "reason", "silent", "options-from",
    "shuffle", "min", "max", "minlength", "maxlength", "format", "low-label", "high-label",
}
OPTION_ATTRS = {"fixed", "other", "exclusive", "skip-to"}
QUOTA_ATTRS = {"question", "value", "target"}

ID_PATTERN = re.compile(r"^[A-Za-z][\w-]*$")
PIPE_PATTERN = re.compile(r"\[([A-Za-z][\w-]*)\]")
LOOKS_LIKE_QID = re.compile(r"^q\d+$", re.IGNORECASE)


# --------------------------------------------------------------------------- small helpers


def _norm(value: str | None) -> str:
    """Compare answers loosely: ignore case and extra spaces."""
    return " ".join((value or "").split()).casefold()


def _to_number(value: str | None) -> float | None:
    try:
        number = float((value or "").strip())
    except ValueError:
        return None
    return number if number == number and abs(number) != float("inf") else None  # no NaN / inf


def _show(number: float | None) -> str:
    """5.0 -> '5', 2.5 -> '2.5'."""
    if number is None:
        return "any"
    return str(int(number)) if float(number).is_integer() else str(number)


def _did_you_mean(word: str, choices: list[str], cutoff: float = 0.6) -> str:
    match = difflib.get_close_matches(word, choices, n=1, cutoff=cutoff)
    return f" Did you mean '{match[0]}'?" if match else ""


def _list(labels: list[str], limit: int = 8) -> str:
    shown = ", ".join(labels[:limit])
    return shown + (f" and {len(labels) - limit} more" if len(labels) > limit else "")


# --------------------------------------------------------------------------- the checker


class _Checker:
    def __init__(self, survey: SurveyDef):
        self.survey = survey
        self.questions = survey.questions
        self.issues: list[Issue] = []
        self.by_id: dict[str, QuestionDef] = {}  # first question with each id
        self.index: dict[str, int] = {}  # id -> position in the file (0, 1, 2...)
        self.skip_ranges: list[tuple[int, int, int]] = []  # (first, last, line) a skip-to can jump over

    # ---- recording problems

    def error(self, line: int, code: str, message: str) -> None:
        self.issues.append(Issue(line, message, code, "error"))

    def warn(self, line: int, code: str, message: str) -> None:
        self.issues.append(Issue(line, message, code, "warning"))

    @staticmethod
    def name(q: QuestionDef) -> str:
        return f"Question {q.qid}" if q.qid else f"The question on line {q.line} (no id)"

    @staticmethod
    def kind(q: QuestionDef) -> str:
        return (q.type or "").strip().lower()

    # ---- main entry

    def run(self) -> list[Issue]:
        self.check_survey_tag()
        self.collect_ids()
        self.collect_skip_ranges()
        for i, q in enumerate(self.questions):
            self.check_question(i, q)
        self.check_quotas()
        return self.issues

    # ---- 1. survey tag

    def check_survey_tag(self) -> None:
        s = self.survey
        self.check_attr_names(s.attrs, SURVEY_ATTRS, "survey", s.line)
        if not s.sid:
            self.error(s.line, "missing_survey_id", 'The <survey> tag needs an id, e.g. id="snack_study".')
        elif not ID_PATTERN.match(s.sid):
            self.error(s.attrs.line_of("id", s.line), "bad_id",
                       f"Survey id '{s.sid}' may only use letters, numbers, '_' and '-', and must start with a letter.")
        if not s.title:
            self.warn(s.line, "missing_title", "The survey has no title, so its id will be shown instead.")
        if s.target is None:
            self.error(s.line, "missing_target", 'The <survey> tag needs a target, e.g. target="200" completes.')
        elif self.whole_number(s.target, minimum=1) is None:
            self.error(s.attrs.line_of("target", s.line), "bad_number",
                       f"Survey target '{s.target}' must be a whole number of at least 1.")
        if not self.questions:
            self.error(s.line, "no_questions", "The survey has no questions.")

    # ---- 2. ids

    def collect_ids(self) -> None:
        used = {q.qid for q in self.questions if q.qid}
        for i, q in enumerate(self.questions):
            qid = q.qid
            if not qid:
                example = f"q{i + 1}" if f"q{i + 1}" not in used else "q_city"
                self.error(q.line, "missing_id",
                           f'The question on line {q.line} has no id. Add one, e.g. id="{example}", '
                           "so rules, quotas and the export can refer to it.")
            elif not ID_PATTERN.match(qid):
                self.error(q.attrs.line_of("id", q.line), "bad_id",
                           f"Question id '{qid}' may only use letters, numbers, '_' and '-', and must start with a letter.")
            elif qid in self.by_id:
                first = self.by_id[qid]
                self.error(q.line, "duplicate_id",
                           f"Question id '{qid}' is used twice (first on line {first.line}). Every question needs its own id.")
            else:
                self.by_id[qid] = q
                self.index[qid] = i

    def collect_skip_ranges(self) -> None:
        """Remember which questions a skip-to can jump over (used for 'may be unanswered')."""
        for i, q in enumerate(self.questions):
            for option in q.options:
                j = self.index.get(option.skip_to or "")
                if j is not None and j > i + 1:
                    self.skip_ranges.append((i + 1, j - 1, option.line))

    # ---- 3. each question

    def check_question(self, i: int, q: QuestionDef) -> None:
        name, kind = self.name(q), self.kind(q)
        self.check_attr_names(q.attrs, QUESTION_ATTRS, "question", q.line)

        if q.type is None:
            self.error(q.line, "missing_type", f'{name} has no type, e.g. type="single".')
        elif kind not in QUESTION_TYPES:
            self.error(q.attrs.line_of("type", q.line), "unknown_type",
                       f"{name} has an unknown type '{q.type}'.{_did_you_mean(kind, QUESTION_TYPES)}")
        if not q.text:
            self.error(q.text_line or q.line, "missing_text", f"{name} has no <text> to show the respondent.")

        self.check_options(q, name, kind)
        if kind in QUESTION_TYPES:
            self.check_type_rules(q, name, kind)
        self.check_options_from(i, q, name, kind)
        self.check_show_if(i, q, name)
        self.check_terminate_on(q, name)
        self.check_skip_to(i, q)
        self.check_piping(i, q, name)

    def check_options(self, q: QuestionDef, name: str, kind: str) -> None:
        seen: dict[str, int] = {}
        for option in q.options:
            self.check_attr_names(option.attrs, OPTION_ATTRS, "option", option.line)
            if not option.label:
                self.error(option.line, "empty_option", f"{name} has an empty <option>.")
                continue
            key = _norm(option.label)
            if key in seen:
                self.error(option.line, "duplicate_option",
                           f"{name} lists the option '{option.label}' twice (first on line {seen[key]}).")
            else:
                seen[key] = option.line
            if option.is_other and kind in QUESTION_TYPES and kind not in CHOICE_TYPES:
                self.warn(option.line, "misplaced_flag", 'other="true" only works on single, multi and dropdown questions.')
            if option.exclusive and kind in QUESTION_TYPES and kind != "multi":
                self.warn(option.line, "misplaced_flag", 'exclusive="true" only makes sense on a multi question.')

    def check_type_rules(self, q: QuestionDef, name: str, kind: str) -> None:
        has_source = q.attrs.has("options-from")
        n_options = len(q.options)

        if kind in CHOICE_TYPES:
            if n_options == 0 and not has_source:
                self.error(q.line, "no_options", f"{name} is a '{kind}' question but has no <option> tags.")
            elif n_options == 1 and not has_source:
                self.warn(q.options[0].line, "few_options", f"{name} has only one option.")
            if kind == "multi":
                self.check_multi_limits(q, name, n_options, has_source)
        elif kind in ("yesno", "consent"):
            if n_options not in (0, 2):
                self.error(q.options[0].line, "bad_yesno_options",
                           f"{name} is a '{kind}' question, so it needs exactly 2 options (or none for Yes / No).")
        elif kind == "matrix":
            if not q.rows:
                self.error(q.line, "matrix_no_rows", f"{name} is a matrix but has no <row> tags (the statements to rate).")
            if n_options == 0:
                self.error(q.line, "matrix_no_scale",
                           f"{name} is a matrix with {len(q.rows)} rows but no answer scale. "
                           "Add <option> tags for the scale, e.g. Agree / Neutral / Disagree.")
            elif n_options == 1:
                self.warn(q.options[0].line, "few_options", f"{name} has a scale with only one option.")
        elif q.options:
            self.warn(q.options[0].line, "options_ignored", f"{name} is a '{kind}' question, so its <option> tags are ignored.")

        if q.rows and kind != "matrix":
            self.warn(q.rows[0].line, "rows_ignored", f"<row> only works on matrix questions; {name} is '{kind}'.")

        if kind == "rating":
            low = self.whole_number_attr(q, "min")
            high = self.whole_number_attr(q, "max")
            low, high = (1 if low is None else low), (5 if high is None else high)
            if low >= high:
                self.error(q.attrs.line_of("min", q.line), "bad_range", f"{name}: min ({low}) must be smaller than max ({high}).")
            elif high - low > 10:
                self.warn(q.attrs.line_of("max", q.line), "wide_scale",
                          f"{name}: a rating scale from {low} to {high} is very long for a phone screen.")
        elif kind == "number":
            low, high = self.number_attr(q, "min"), self.number_attr(q, "max")
            if low is not None and high is not None and low > high:
                self.error(q.attrs.line_of("min", q.line), "bad_range",
                           f"{name}: min ({_show(low)}) must not be larger than max ({_show(high)}).")
        elif kind in ("text", "longtext"):
            low = self.whole_number_attr(q, "minlength")
            high = self.whole_number_attr(q, "maxlength")
            if low is not None and high is not None and low > high:
                self.error(q.attrs.line_of("minlength", q.line), "bad_range",
                           f"{name}: minlength ({low}) must not be larger than maxlength ({high}).")
        elif kind == "formatted":
            fmt = q.attrs.get("format")
            if not fmt:
                self.error(q.line, "missing_format", f'{name} is a formatted question but has no format (pincode, phone or email).')
            elif fmt.lower() not in FORMATS:
                self.error(q.attrs.line_of("format", q.line), "unknown_format",
                           f"{name} has an unknown format '{fmt}'. Use pincode, phone or email."
                           f"{_did_you_mean(fmt.lower(), FORMATS)}")
        elif kind == "info" and q.required:
            self.warn(q.attrs.line_of("required", q.line), "required_ignored",
                      f"{name} is an information screen with nothing to answer, so 'required' is ignored.")

    def check_multi_limits(self, q: QuestionDef, name: str, n_options: int, has_source: bool) -> None:
        low = self.whole_number_attr(q, "min", minimum=0)
        high = self.whole_number_attr(q, "max", minimum=1)
        if low is not None and high is not None and low > high:
            self.error(q.attrs.line_of("min", q.line), "bad_range", f"{name}: min ({low}) must not be larger than max ({high}).")
        if high is not None and not has_source and n_options and high > n_options:
            self.warn(q.attrs.line_of("max", q.line), "max_too_big",
                      f"{name}: max={high} but there are only {n_options} options.")

    # ---- 4. rules that point at other questions

    def check_options_from(self, i: int, q: QuestionDef, name: str, kind: str) -> None:
        source_id = q.attrs.get("options-from")
        if source_id is None:
            return
        line = q.attrs.line_of("options-from", q.line)
        if kind in QUESTION_TYPES and kind not in CHOICE_TYPES:
            self.error(line, "misplaced_rule", f"options-from only works on single, multi and dropdown questions; {name} is '{kind}'.")
        source = self.reference(i, q, source_id, line, "options-from", direction="earlier")
        if source is None:
            return
        if self.kind(source) not in CHOICE_TYPES or not source.options:
            self.error(line, "bad_options_source",
                       f"{name} copies options from {source_id}, but {source_id} is not a single / multi / dropdown question with options.")
        elif reason := self.may_be_unanswered(source):
            self.warn(line, "may_be_unanswered",
                      f"{name} copies the answers of {source_id}, but {source_id} may be unanswered ({reason}). "
                      f"{name} would then have no options.")

    def check_show_if(self, i: int, q: QuestionDef, name: str) -> None:
        rule = q.attrs.get("show-if")
        if rule is None:
            return
        line = q.attrs.line_of("show-if", q.line)
        try:
            tree = parse_condition(rule)
        except ConditionError as exc:
            self.error(line, "bad_condition", f'{name}: show-if="{rule}" cannot be read. {exc}')
            return
        for test in comparisons(tree):
            target = self.reference(i, q, test.qid, line, "show-if", direction="earlier")
            if target is None:
                continue
            problem = self.value_problem(target, test.op, test.value)
            if problem:
                self.error(line, "unknown_value", f'{name}: show-if "{test.qid}{test.op}{test.value}" can never be true. {problem}')

    def check_terminate_on(self, q: QuestionDef, name: str) -> None:
        value = q.attrs.get("terminate-on")
        if value is None:
            return
        line = q.attrs.line_of("terminate-on", q.line)
        problem = self.value_problem(q, "=", value)
        if problem:
            self.error(line, "unknown_value", f'{name}: terminate-on="{value}" can never happen. {problem}')
        if not q.attrs.get("reason") and not q.silent:
            self.warn(line, "missing_reason",
                      f'{name} ends the survey for some people but has no reason="...". The reason is saved and shown in the dashboard.')

    def check_skip_to(self, i: int, q: QuestionDef) -> None:
        for option in q.options:
            if option.skip_to is not None:
                line = option.attrs.line_of("skip-to", option.line)
                self.reference(i, q, option.skip_to, line, f"the option '{option.label}' (skip-to)", direction="later")

    def check_piping(self, i: int, q: QuestionDef, name: str) -> None:
        """[q7] inside text shows the answer to q7. It must be asked earlier."""
        places = [(q.text, q.text_line or q.line)]
        places += [(o.label, o.line) for o in q.options] + [(r.label, r.line) for r in q.rows]
        warned: set[str] = set()
        for text, line in places:
            for match in PIPE_PATTERN.finditer(text or ""):
                ref = match.group(1)
                if ref not in self.by_id and not LOOKS_LIKE_QID.match(ref):
                    continue  # ordinary text in brackets, e.g. [optional]
                target = self.reference(i, q, ref, line, f"[{ref}]", direction="earlier")
                if target is None:
                    continue
                if self.kind(target) in ("matrix", "info"):
                    self.error(line, "bad_piping", f"{name} shows [{ref}], but {ref} is a {self.kind(target)} question with no single answer to show.")
                elif ref not in warned and (reason := self.may_be_unanswered(target)):
                    warned.add(ref)
                    self.warn(line, "may_be_unanswered",
                              f"{name} shows the answer to {ref}, but {ref} may be unanswered ({reason}). [{ref}] would then be blank.")

    def reference(self, i: int, q: QuestionDef, ref: str, line: int, what: str, direction: str) -> QuestionDef | None:
        """Check that `ref` is a real question on the right side of question number i.
        Returns the question it points to (even if it is on the wrong side), or None."""
        name = self.name(q)
        target = self.by_id.get(ref)
        if target is None:
            allowed = [qid for qid, j in self.index.items() if (j < i if direction == "earlier" else j > i)]
            self.error(line, "unknown_reference",
                       f"{name}: {what} points to '{ref}', but there is no question with that id."
                       f"{_did_you_mean(ref, allowed, cutoff=0.75)}")
            return None
        j = self.index[ref]
        if target is q:
            self.error(line, "self_reference", f"{name}: {what} points to the question itself.")
            return None
        if direction == "earlier" and j > i:
            self.error(line, "forward_reference",
                       f"{name}: {what} uses {ref}, but {ref} comes later (line {target.line}). "
                       "A rule can only use answers that were given before this question.")
        elif direction == "later" and j < i:
            self.error(line, "backward_skip",
                       f"{name}: {what} jumps back to {ref} (line {target.line}). skip-to can only jump forward.")
        return target

    # ---- what answers a question can have

    def answer_space(self, q: QuestionDef) -> tuple[str, object] | None:
        """What a question's answer can look like:
            ("choice", [labels])        pick from options
            ("range", (low, high, ints)) a number, maybe limited
            ("free", None)              typed text, anything goes
            ("none", reason)            nothing to compare (info, matrix)
        None means "we cannot tell" (e.g. broken type): skip the check, the cause is reported already."""
        kind = self.kind(q)
        if kind == "info":
            return ("none", f"{q.qid} is an information screen with no answer.")
        if kind == "matrix":
            return ("none", f"{q.qid} is a matrix (one answer per row), so it cannot be compared with one value.")
        if kind == "rating":
            low, high = self.whole_number_attr(q, "min", report=False), self.whole_number_attr(q, "max", report=False)
            return ("range", (1 if low is None else low, 5 if high is None else high, True))
        if kind == "nps":
            return ("range", (0, 10, True))
        if kind == "number":
            return ("range", (self.number_attr(q, "min", report=False), self.number_attr(q, "max", report=False), False))
        if kind in ("text", "longtext", "formatted"):
            return ("free", None)

        labels = [o.label for o in q.options if o.label]
        source_id = q.attrs.get("options-from")
        if source_id:
            source = self.by_id.get(source_id)
            if source is None:
                return None
            labels = [o.label for o in source.options if o.label] + labels
        if not labels and kind in ("yesno", "consent"):
            labels = ["Yes", "No"]
        return ("choice", labels) if labels else None

    def value_problem(self, q: QuestionDef, op: str, value: str) -> str | None:
        """Why `answer op value` can never be true for question q, or None if it can."""
        space = self.answer_space(q)
        if space is None:
            return None
        kind, data = space
        if kind == "none":
            return str(data)
        if kind == "free":
            if op in ORDER_OPERATORS:
                return f"'{op}' only works with number, rating and nps questions; {q.qid} is a text answer."
            return None
        if kind == "choice":
            if op in ORDER_OPERATORS:
                return f"'{op}' only works with number, rating and nps questions; {q.qid} is a choice question."
            if _norm(value) in {_norm(label) for label in data}:
                return None
            hint = _did_you_mean(value, data)
            return f"'{value}' is not one of the answers of {q.qid} ({_list(data)}).{hint}"

        low, high, whole = data
        number = _to_number(value)
        type_name = self.kind(q)
        if number is None:
            return f"{q.qid} is a {type_name} question, so '{value}' can never be its answer (it must be a number)."
        if whole and not number.is_integer():
            return f"{q.qid} only takes whole numbers, so '{value}' can never be its answer."
        too_low = low is not None and number < low
        too_high = high is not None and number > high
        if (op == "=" and (too_low or too_high)):
            return f"{value} is outside the allowed range of {q.qid} ({_show(low)} to {_show(high)})."
        return None

    def answered_elsewhere(self, value: str, exclude: QuestionDef) -> str:
        """Hint for a value given to the wrong question: which question does have it?"""
        for other in self.questions:
            if other is exclude:
                continue
            if any(_norm(o.label) == _norm(value) for o in other.options):
                who = other.qid or f"the question on line {other.line} (it has no id yet)"
                return f" '{value}' is an answer of {who}; did you mean that question?"
        return ""

    def may_be_unanswered(self, q: QuestionDef) -> str | None:
        if not q.required:
            return "it is optional"
        if q.attrs.has("show-if"):
            return "it has a show-if rule"
        position = self.index.get(q.qid or "")
        for first, last, line in self.skip_ranges:
            if position is not None and first <= position <= last:
                return f"the skip-to on line {line} can jump over it"
        return None

    # ---- 5. quotas

    def check_quotas(self) -> None:
        survey_target = self.whole_number(self.survey.target or "", minimum=1)
        seen: dict[tuple[str, str], int] = {}
        valid: dict[str, list[tuple[str, int, int]]] = {}  # qid -> [(value, target, line)]

        for quota in self.survey.quotas:
            self.check_attr_names(quota.attrs, QUOTA_ATTRS, "quota", quota.line)
            missing = [a for a in ("question", "value", "target") if not quota.attrs.get(a)]
            if missing:
                self.error(quota.line, "quota_missing_field", f"The quota needs {', '.join(missing)}.")
            target = None
            if quota.target:
                target = self.whole_number(quota.target, minimum=1)
                if target is None:
                    self.error(quota.attrs.line_of("target", quota.line), "bad_number",
                               f"Quota target '{quota.target}' must be a whole number of at least 1.")
            if not quota.question or not quota.value:
                continue

            label = f"Quota {quota.question}={quota.value}"
            question = self.by_id.get(quota.question)
            if question is None:
                self.error(quota.attrs.line_of("question", quota.line), "unknown_reference",
                           f"{label}: there is no question with id '{quota.question}'."
                           f"{_did_you_mean(quota.question, list(self.by_id), cutoff=0.75)}")
                continue
            problem = self.value_problem(question, "=", quota.value)
            if problem:
                self.error(quota.line, "unknown_value",
                           f"{label} can never be filled. {problem}{self.answered_elsewhere(quota.value, question)}")
                continue
            key = (quota.question, _norm(quota.value))
            if key in seen:
                self.error(quota.line, "duplicate_quota", f"{label} is set twice (first on line {seen[key]}).")
                continue
            seen[key] = quota.line
            if target is not None:
                valid.setdefault(quota.question, []).append((quota.value, target, quota.line))
                if survey_target and target > survey_target:
                    self.warn(quota.line, "quota_over_target",
                              f"{label} wants {target} people, more than the survey target of {survey_target}.")

        # If every answer of a question has a quota, the quotas together cap the survey.
        for qid, items in valid.items():
            space = self.answer_space(self.by_id[qid])
            if not survey_target or not space or space[0] != "choice":
                continue
            covered = {_norm(value) for value, _, _ in items}
            total = sum(target for _, target, _ in items)
            if covered >= {_norm(label) for label in space[1]} and total < survey_target:
                self.warn(items[-1][2], "quotas_below_target",
                          f"The quotas on {qid} add up to {total}, so the survey can never reach its target of {survey_target}.")

    # ---- attribute helpers

    def check_attr_names(self, attrs: Attrs, allowed: set[str], tag: str, line: int) -> None:
        """A close typo (requried) is an error, because the rule would silently not apply.
        Anything else is a warning: it is simply ignored."""
        for key in attrs.values:
            if key in allowed:
                continue
            where = attrs.line_of(key, line)
            hint = _did_you_mean(key, sorted(allowed), cutoff=0.75)
            if hint:
                self.error(where, "unknown_attribute", f"Unknown attribute '{key}' on <{tag}>.{hint}")
            else:
                self.warn(where, "unknown_attribute", f"Unknown attribute '{key}' on <{tag}>; it will be ignored.")

    @staticmethod
    def whole_number(value: str, minimum: int | None = None) -> int | None:
        try:
            number = int(value.strip())
        except (ValueError, AttributeError):
            return None
        return None if minimum is not None and number < minimum else number

    def whole_number_attr(self, q: QuestionDef, attr: str, minimum: int | None = None, report: bool = True) -> int | None:
        raw = q.attrs.get(attr)
        if raw is None:
            return None
        number = self.whole_number(raw, minimum)
        if number is None and report:
            floor = f" of at least {minimum}" if minimum is not None else ""
            self.error(q.attrs.line_of(attr, q.line), "bad_number",
                       f"{self.name(q)}: {attr}='{raw}' must be a whole number{floor}.")
        return number

    def number_attr(self, q: QuestionDef, attr: str, report: bool = True) -> float | None:
        raw = q.attrs.get(attr)
        if raw is None:
            return None
        number = _to_number(raw)
        if number is None and report:
            self.error(q.attrs.line_of(attr, q.line), "bad_number", f"{self.name(q)}: {attr}='{raw}' must be a number.")
        return number


# --------------------------------------------------------------------------- public


def validate(survey: SurveyDef) -> list[Issue]:
    """All content problems of a parsed survey. Never raises."""
    return _Checker(survey).run()


def check_questionnaire(text: str) -> ParseResult:
    """Read and check questionnaire text in one go: structure problems + content problems,
    sorted by line. This is what the upload screen and the CLI use."""
    parsed = parse_questionnaire(text)
    issues = list(parsed.issues)
    if parsed.survey is not None:
        issues += validate(parsed.survey)
    issues.sort(key=lambda issue: (issue.line, issue.severity != "error"))
    return ParseResult(parsed.survey, issues)
