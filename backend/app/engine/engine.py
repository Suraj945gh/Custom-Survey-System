"""The survey engine: given the questions and the answers so far, what happens next?

It is pure Python (no database, no web), so every rule can be tested like a story.
It accepts any question objects with these attributes:
    qid, type, text, required, options (list of dicts), rows (list), rules (dict)
which is true for the `questions` table rows and for SurveyEngine.from_spec() in tests.

The central idea is THE WALK. Starting at question 1, walk forward:
    - a question whose show-if is false (or whose copied options are empty) is skipped
    - an answered question: follow its skip-to if the picked option has one, else go on
    - the first visible question without an answer is where the respondent is now
Because the walk is redone from the start every time, going Back and changing an answer
automatically changes everything after it: newly hidden questions drop out of the path.

Ending a response (decision D6):
    - consent "No" ends it at once
    - otherwise failed terminate-on rules and full quotas are collected while the respondent is
      in the SCREENING SECTION (up to the last question that has terminate-on or a quota).
      When they move past it, the response ends with all reasons, joined by " | ".
    - reasons are worked out again from all current answers each time, so Back + change clears them
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from app.questionnaire.conditions import ORDER_OPERATORS, Compare, ConditionError, evaluate, parse_condition
from app.questionnaire.validator import PIPE_PATTERN

from .answers import NUMERIC, Given, Option, as_number, display, matches, norm, settings_of, show_number

CONSENT_REFUSED = "Did not give consent"


# --------------------------------------------------------------------------- plain question objects (tests, previews)


@dataclass
class QuestionSpec:
    qid: str
    type: str
    text: str = ""
    required: bool = False
    options: list[dict[str, Any]] = field(default_factory=list)
    rows: list[str] = field(default_factory=list)
    rules: dict[str, Any] = field(default_factory=dict)


@dataclass
class QuotaSpec:
    question_qid: str
    value: str
    target: int


# --------------------------------------------------------------------------- results


@dataclass
class Walk:
    path: list[str]  # visible questions in order, up to and including the current one
    current: str | None  # first unanswered visible question; None = nothing left
    skipped: set[str]  # questions passed over (hidden or jumped over by skip-to)
    active: dict[str, Given]  # answers that are on the path (the only ones that count)


@dataclass
class Reason:
    text: str
    silent: bool = False


@dataclass
class Outcome:
    """What happens after an answer."""

    kind: str  # "continue" | "terminated" | "complete"
    next_qid: str | None = None
    reasons: list[Reason] = field(default_factory=list)

    @property
    def silent(self) -> bool:
        return bool(self.reasons) and all(r.silent for r in self.reasons)


def join_reasons(reasons: list[Reason]) -> str:
    seen: list[str] = []
    for reason in reasons:
        if reason.text not in seen:
            seen.append(reason.text)
    return " | ".join(seen)


# --------------------------------------------------------------------------- the engine


class SurveyEngine:
    def __init__(self, questions, quotas=()):
        self.questions = list(questions)
        self.quotas = list(quotas)
        self.index = {q.qid: i for i, q in enumerate(self.questions)}
        self.by_id = {q.qid: q for q in self.questions}
        self.conditions = {}
        for q in self.questions:
            rule = (q.rules or {}).get("show_if")
            if rule:
                try:
                    self.conditions[q.qid] = parse_condition(rule)
                except ConditionError:  # cannot happen for an approved survey; be safe anyway
                    pass
        quota_qids = {quota.question_qid for quota in self.quotas}
        screening = [i for i, q in enumerate(self.questions) if (q.rules or {}).get("terminate_on") or q.qid in quota_qids]
        self.screening_end = max(screening) if screening else -1

    @classmethod
    def from_spec(cls, spec: dict) -> "SurveyEngine":
        """Build from survey_spec() output (used by tests)."""
        questions = [
            QuestionSpec(q["qid"], q["type"], q["text"], q["required"], q["options"], q["rows"], q["rules"])
            for q in spec["questions"]
        ]
        quotas = [QuotaSpec(q["question"], q["value"], q["target"]) for q in spec["quotas"]]
        return cls(questions, quotas)

    # ---- the walk

    def walk(self, answers: dict[str, Given]) -> Walk:
        path: list[str] = []
        skipped: set[str] = set()
        active: dict[str, Given] = {}
        i = 0
        while i < len(self.questions):
            q = self.questions[i]
            if not self.is_visible(q, active):
                skipped.add(q.qid)
                i += 1
                continue
            path.append(q.qid)
            given = answers.get(q.qid)
            if given is None:
                return Walk(path, q.qid, skipped, active)
            active[q.qid] = given
            target = self.skip_target(q, given)
            if target is not None and self.index.get(target, -1) > i:
                skipped.update(self.questions[j].qid for j in range(i + 1, self.index[target]))
                i = self.index[target]
            else:
                i += 1
        return Walk(path, None, skipped, active)

    def is_visible(self, q, active: dict[str, Given]) -> bool:
        condition = self.conditions.get(q.qid)
        if condition is not None and not evaluate(condition, lambda test: self.test(test, active)):
            return False
        if (q.rules or {}).get("options_from") and not self.copied_options(q, active):
            return False  # nothing was picked earlier, so there is nothing to choose from
        return True

    def skip_target(self, q, given: Given) -> str | None:
        picked = given.value if isinstance(given.value, list) else [given.value]
        for option in q.options or []:
            if option.get("skip_to") and option["label"] in picked:
                return option["skip_to"]
        return None

    def test(self, test: Compare, active: dict[str, Given]) -> bool:
        """One show-if comparison against the answers on the path. No answer = false."""
        q, given = self.by_id.get(test.qid), active.get(test.qid)
        if q is None or given is None or given.value is None:
            return False
        if q.type in NUMERIC:
            have, want = as_number(given.value), as_number(test.value)
            if have is None or want is None:
                return False
            return {
                "=": have == want, "!=": have != want, ">": have > want,
                ">=": have >= want, "<": have < want, "<=": have <= want,
            }[test.op]
        if test.op in ORDER_OPERATORS:
            return False
        found = matches(given.value, given.other_text, test.value)
        return found if test.op == "=" else not found

    def next_after(self, qid: str, walk: Walk) -> str | None:
        """The question after `qid` on the path (may already be answered, after going Back)."""
        if qid not in walk.path:
            return walk.current
        position = walk.path.index(qid)
        return walk.path[position + 1] if position + 1 < len(walk.path) else None

    def previous_before(self, qid: str, walk: Walk) -> str | None:
        if qid not in walk.path:
            return walk.path[-1] if walk.path else None
        position = walk.path.index(qid)
        return walk.path[position - 1] if position > 0 else None

    def progress(self, qid: str | None) -> int:
        if qid is None or not self.questions:
            return 100
        return round(100 * self.index[qid] / len(self.questions))

    # ---- options, piping, screens

    def copied_options(self, q, active: dict[str, Given]) -> list[Option]:
        """options-from: the options picked in the source question, with the typed 'Other' text
        used instead of 'Other (specify)'. 'None of these' style options are not copied."""
        source_id = (q.rules or {}).get("options_from")
        source, given = self.by_id.get(source_id), active.get(source_id)
        if source is None or given is None or given.value is None:
            return []
        picked = given.value if isinstance(given.value, list) else [given.value]
        copied = []
        for option in source.options or []:
            if option["label"] not in picked or option.get("exclusive"):
                continue
            if option.get("other") and given.other_text:
                copied.append(Option(given.other_text, given.other_text))
            else:
                copied.append(Option(option["label"], option["label"]))
        return copied

    def options_for(self, q, active: dict[str, Given]) -> list[Option]:
        own = [
            Option(o["label"], self.pipe(o["label"], active), bool(o.get("fixed")), bool(o.get("other")),
                   bool(o.get("exclusive")), o.get("skip_to"))
            for o in q.options or []
        ]
        if q.type in ("yesno", "consent") and not own:
            own = [Option("Yes", "Yes"), Option("No", "No")]
        if (q.rules or {}).get("options_from"):
            return self.copied_options(q, active) + own
        return own

    def ordered_options(self, q, active, saved_order: list[str] | None, rng: random.Random | None = None):
        """Options in the order this respondent sees them.
        shuffle="true": the non-fixed options are shuffled once, fixed ones stay last, and the order
        is saved so Back and resume show the same order. Returns (options, order_to_save or None)."""
        options = self.options_for(q, active)
        if not (q.rules or {}).get("shuffle") or q.type == "matrix":
            return options, None
        values = [o.value for o in options]
        if saved_order and sorted(saved_order) == sorted(values):
            by_value = {o.value: o for o in options}
            return [by_value[v] for v in saved_order], None
        movable = [o for o in options if not o.fixed]
        (rng or random.Random()).shuffle(movable)
        ordered = movable + [o for o in options if o.fixed]
        return ordered, [o.value for o in ordered]

    def pipe(self, text: str, active: dict[str, Given]) -> str:
        """Replace [q7] with the answer to q7 ('' if it was not answered)."""

        def answer_of(match):
            qid = match.group(1)
            if qid not in self.by_id:
                return match.group(0)
            return display(self.by_id[qid], active.get(qid))

        return PIPE_PATTERN.sub(answer_of, text or "")

    def render(self, q, active: dict[str, Given], options: list[Option]) -> dict[str, Any]:
        """Everything the phone screen needs to draw one question."""
        s = settings_of(q)
        rules = q.rules or {}
        settings = {
            key: value
            for key, value in {
                "min": show_number(s.min) if s.min is not None else None,
                "max": show_number(s.max) if s.max is not None else None,
                "minlength": s.minlength, "maxlength": s.maxlength, "format": s.format,
                "low_label": rules.get("low_label"), "high_label": rules.get("high_label"),
            }.items()
            if value is not None
        }
        return {
            "qid": q.qid,
            "type": q.type,
            "text": self.pipe(q.text, active),
            "required": bool(q.required),
            "options": [
                {"value": o.value, "label": o.label, "other": o.other, "exclusive": o.exclusive} for o in options
            ],
            "rows": [self.pipe(r, active) for r in (q.rows or [])],
            "settings": settings,
        }

    # ---- cleaning up after a change

    def stale_answers(self, walk: Walk) -> set[str]:
        """Answers that no longer fit after an earlier answer changed, e.g. q7 = 'Apple' while
        Apple is no longer picked in q6. They are removed so the question is asked again."""
        stale = set()
        for qid, given in walk.active.items():
            q = self.by_id[qid]
            if not (q.rules or {}).get("options_from") or given.value is None:
                continue
            allowed = {norm(o.value) for o in self.options_for(q, walk.active)}
            picked = given.value if isinstance(given.value, list) else [given.value]
            if any(norm(item) not in allowed for item in picked):
                stale.add(qid)
        return stale

    def tidy(self, answers: dict[str, Given]) -> set[str]:
        """Remove answers that no longer count: questions now hidden or jumped over, and answers
        that no longer fit their options. Changes `answers` in place; returns the removed ids."""
        removed: set[str] = set()
        for _ in range(len(self.questions) + 1):
            walk = self.walk(answers)
            drop = {qid for qid in walk.skipped if qid in answers} | self.stale_answers(walk)
            if not drop:
                break
            for qid in drop:
                answers.pop(qid, None)
            removed |= drop
        return removed

    # ---- ending

    def consent_refused(self, q, given: Given) -> bool:
        if q.type != "consent" or given.value is None:
            return False
        labels = [o["label"] for o in q.options] if q.options else ["Yes", "No"]
        return len(labels) >= 2 and norm(given.value) == norm(labels[1])

    def end_reasons(self, active: dict[str, Given], full_quotas: set[tuple[str, str]]) -> list[Reason]:
        """Every reason this respondent cannot continue, given ALL current answers."""
        reasons: list[Reason] = []
        for qid, given in active.items():
            q = self.by_id[qid]
            if self.consent_refused(q, given):
                reasons.append(Reason(CONSENT_REFUSED))
            rules = q.rules or {}
            wanted = rules.get("terminate_on")
            if wanted and matches(given.value, given.other_text, wanted):
                reasons.append(Reason(rules.get("reason") or "Not eligible", bool(rules.get("silent"))))
        for quota in self.quotas:
            given = active.get(quota.question_qid)
            if (quota.question_qid, norm(quota.value)) in full_quotas and given and matches(given.value, given.other_text, quota.value):
                reasons.append(Reason(f"Quota full: {quota.value}"))
        return reasons

    def after_answer(self, qid: str, answers: dict[str, Given], full_quotas: set[tuple[str, str]]) -> Outcome:
        walk = self.walk(answers)
        q, given = self.by_id[qid], answers.get(qid)
        if given is not None and self.consent_refused(q, given):
            return Outcome("terminated", reasons=[Reason(CONSENT_REFUSED)])
        next_qid = self.next_after(qid, walk)
        past_screening = next_qid is None or self.index[next_qid] > self.screening_end
        if past_screening:
            reasons = self.end_reasons(walk.active, full_quotas)
            if reasons:
                return Outcome("terminated", reasons=reasons)
        if next_qid is None and walk.current is None:
            return Outcome("complete")
        return Outcome("continue", next_qid=next_qid or walk.current)
