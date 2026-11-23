"""Engine stories: respondents walking through the sample survey.

Each test reads like a story: answer this, then that, and check what the engine does.
"""

import random

import pytest

from app.engine import AnswerError, SurveyEngine, clean_answer
from app.questionnaire import parse_questionnaire
from app.questionnaire.spec import survey_spec

MATRIX = {
    "The battery lasts a full day": "Agree",
    "The camera takes good photos": "Agree",
    "It works smoothly without lag": "Neutral",
    "It was good value for money": "Agree",
}


@pytest.fixture
def engine(sample_text):
    return SurveyEngine.from_spec(survey_spec(parse_questionnaire(sample_text).survey))


def engine_of(body: str) -> SurveyEngine:
    text = f'<survey id="s" title="S" target="10">\n{body}\n</survey>'
    result = parse_questionnaire(text)
    return SurveyEngine.from_spec(survey_spec(result.survey))


class Respondent:
    """One person clicking through, the same way the API does it."""

    def __init__(self, engine, full_quotas=()):
        self.engine = engine
        self.answers = {}
        self.full = set(full_quotas)
        self.outcome = None

    def answer(self, qid, value=None, other=None):
        walk = self.engine.walk(self.answers)
        assert qid in walk.path, f"{qid} is not on screen; the path is {walk.path}"
        q = self.engine.by_id[qid]
        self.answers[qid] = clean_answer(q, value, other, self.engine.options_for(q, walk.active))
        self.engine.tidy(self.answers)
        self.outcome = self.engine.after_answer(qid, self.answers, self.full)
        return self

    def answers_in_order(self, *pairs):
        for pair in pairs:
            self.answer(*pair)
        return self

    @property
    def now(self):
        """The question on screen next (None when the response has ended or is complete)."""
        return self.outcome.next_qid if self.outcome.kind == "continue" else None

    @property
    def walk(self):
        return self.engine.walk(self.answers)

    def screen(self, qid):
        walk = self.walk
        q = self.engine.by_id[qid]
        return self.engine.render(q, walk.active, self.engine.options_for(q, walk.active))


SCREENING_OK = [("q0",), ("q1", "Yes"), ("q2", 30), ("q3", "Male"), ("q4", "Mumbai"), ("q5", "Yes")]


def screened(engine, **changes):
    """A respondent who got through screening (with optional changed answers)."""
    person = Respondent(engine)
    for step in SCREENING_OK:
        qid = step[0]
        person.answer(qid, changes.get(qid, step[1] if len(step) > 1 else None))
    return person


# --------------------------------------------------------------------------- the main paths


class TestHappyPath:
    def test_starts_at_the_first_question(self, engine):
        assert engine.walk({}).current == "q0"
        assert engine.walk({}).path == ["q0"]

    def test_complete_walk_through_with_other_text_and_piping(self, engine):
        person = screened(engine)
        assert person.now == "q6"
        person.answer("q6", ["Samsung", "Other (specify)"], other="Nokia")

        # q7 copies the brands picked in q6, using the typed text instead of "Other (specify)"
        assert [o["label"] for o in person.screen("q7")["options"]] == ["Samsung", "Nokia"]
        person.answer("q7", "Nokia")
        # piping [q7] shows the typed brand
        assert person.screen("q8")["text"] == "How happy are you with your Nokia phone?"

        person.answer("q8", 4)
        assert person.now == "q10"  # q9 is only for unhappy people
        person.answers_in_order(("q10", 9), ("q11", MATRIX), ("q12", "Yes"), ("q13", 30000),
                                ("q14", ["YouTube reviews"]), ("q15", "Yes"), ("q16", "Ravi"))
        assert person.now == "q17"
        person.answer("q17", "400001")
        assert person.outcome.kind == "complete"

    def test_progress_moves_forward(self, engine):
        assert engine.progress("q0") == 0
        assert 40 < engine.progress("q9") < 60
        assert engine.progress(None) == 100


class TestSkipAndShowIf:
    def test_q12_no_skips_to_q16(self, engine):
        person = screened(engine).answers_in_order(
            ("q6", ["Apple"]), ("q7", "Apple"), ("q8", 3), ("q10", 8), ("q11", MATRIX), ("q12", "No")
        )
        assert person.now == "q16"
        assert {"q13", "q14", "q15"} <= person.walk.skipped

    def test_q15_only_for_mumbai_and_yes(self, engine):
        pune = screened(engine, q4="Pune").answers_in_order(
            ("q6", ["Apple"]), ("q7", "Apple"), ("q8", 3), ("q10", 8), ("q11", MATRIX),
            ("q12", "Yes"), ("q13", 20000), ("q14", ["Shop visit"]),
        )
        assert pune.now == "q16"

        mumbai = screened(engine).answers_in_order(
            ("q6", ["Apple"]), ("q7", "Apple"), ("q8", 3), ("q10", 8), ("q11", MATRIX),
            ("q12", "Yes"), ("q13", 20000), ("q14", ["Shop visit"]),
        )
        assert mumbai.now == "q15"

    @pytest.mark.parametrize("rating, shown", [(1, True), (2, True), (3, False), (5, False)])
    def test_q9_only_for_ratings_1_and_2(self, engine, rating, shown):
        person = screened(engine).answers_in_order(("q6", ["Apple"]), ("q7", "Apple"), ("q8", rating))
        assert (person.now == "q9") is shown

    def test_back_and_change_rating_brings_q9_in(self, engine):
        person = screened(engine).answers_in_order(("q6", ["Apple"]), ("q7", "Apple"), ("q8", 5), ("q10", 7))
        person.answer("q8", 1)  # went Back and changed
        assert person.now == "q9"
        assert "q10" in person.answers  # later answers are kept, not lost

    def test_changing_q12_to_no_removes_answers_that_no_longer_count(self, engine):
        person = screened(engine).answers_in_order(
            ("q6", ["Apple"]), ("q7", "Apple"), ("q8", 3), ("q10", 8), ("q11", MATRIX),
            ("q12", "Yes"), ("q13", 20000), ("q14", ["Shop visit"]),
        )
        person.answer("q12", "No")
        assert "q13" not in person.answers and "q14" not in person.answers
        assert person.now == "q16"


class TestOptionsFrom:
    def test_none_of_these_is_not_copied(self):
        e = engine_of(
            '<question id="q1" type="multi" required><text>A</text><option>X</option><option exclusive="true">None</option></question>\n'
            '<question id="q2" type="single" required options-from="q1"><text>B</text></question>\n'
            '<question id="q3" type="text"><text>C</text></question>'
        )
        person = Respondent(e).answer("q1", ["None"])
        assert person.now == "q3"  # q2 had nothing to choose from, so it is skipped

    def test_changing_the_source_asks_again(self, engine):
        person = screened(engine).answers_in_order(("q6", ["Apple", "Samsung"]), ("q7", "Apple"), ("q8", 4))
        person.answer("q6", ["Samsung"])  # went back, Apple no longer picked
        assert "q7" not in person.answers
        assert person.walk.current == "q7"


# --------------------------------------------------------------------------- ending a response


class TestTermination:
    def test_consent_no_ends_at_once(self, engine):
        person = Respondent(engine).answer("q0").answer("q1", "No")
        assert person.outcome.kind == "terminated"
        assert [r.text for r in person.outcome.reasons] == ["Did not give consent"]

    def test_other_city_ends_after_screening_with_its_reason(self, engine):
        person = Respondent(engine).answers_in_order(("q0",), ("q1", "Yes"), ("q2", 30), ("q3", "Male"), ("q4", "Other city"))
        assert person.now == "q5"  # still in screening: keep collecting
        person.answer("q5", "Yes")
        assert person.outcome.kind == "terminated"
        assert [r.text for r in person.outcome.reasons] == ["City not in scope"]

    def test_two_failed_rules_are_both_saved(self, engine):
        person = screened(engine, q4="Other city", q5="No")
        assert person.outcome.kind == "terminated"
        assert [r.text for r in person.outcome.reasons] == ["City not in scope", "Not a smartphone user"]

    def test_back_and_change_clears_a_failed_rule(self, engine):
        person = Respondent(engine).answers_in_order(("q0",), ("q1", "Yes"), ("q2", 30), ("q3", "Male"), ("q4", "Other city"))
        person.answer("q4", "Pune")  # Back, changed the city
        person.answer("q5", "Yes")
        assert person.outcome.kind == "continue" and person.now == "q6"

    def test_full_quota_ends_the_response(self, engine):
        person = Respondent(engine, full_quotas={("q3", "male")})
        for step in SCREENING_OK:
            person.answer(*step)
        assert person.outcome.kind == "terminated"
        assert [r.text for r in person.outcome.reasons] == ["Quota full: Male"]

    def test_full_quota_and_failed_rule_together(self, engine):
        person = Respondent(engine, full_quotas={("q4", "mumbai")})
        person.answers_in_order(("q0",), ("q1", "Yes"), ("q2", 30), ("q3", "Male"), ("q4", "Mumbai"), ("q5", "No"))
        assert [r.text for r in person.outcome.reasons] == ["Not a smartphone user", "Quota full: Mumbai"]

    def test_quota_for_another_group_does_not_matter(self, engine):
        person = Respondent(engine, full_quotas={("q3", "female")})
        for step in SCREENING_OK:
            person.answer(*step)
        assert person.outcome.kind == "continue"

    def test_silent_termination(self):
        e = engine_of('<question id="q1" type="yesno" required terminate-on="No" reason="Low fit" silent="true"><text>A</text></question>\n'
                      '<question id="q2" type="text"><text>B</text></question>')
        outcome = Respondent(e).answer("q1", "No").outcome
        assert outcome.kind == "terminated" and outcome.silent
        assert outcome.reasons[0].text == "Low fit"


# --------------------------------------------------------------------------- shuffle


class TestShuffle:
    def test_fixed_options_stay_last_and_order_is_reused(self, engine):
        q6 = engine.by_id["q6"]
        options, order = engine.ordered_options(q6, {}, None, random.Random(1))
        assert options[-1].value == "Other (specify)"
        assert order is not None and len(order) == 7
        again, new = engine.ordered_options(q6, {}, order, random.Random(99))
        assert [o.value for o in again] == order and new is None

    def test_shuffle_really_shuffles(self, engine):
        q6 = engine.by_id["q6"]
        orders = {tuple(engine.ordered_options(q6, {}, None, random.Random(seed))[1]) for seed in range(10)}
        assert len(orders) > 1

    def test_no_shuffle_keeps_file_order(self, engine):
        options, order = engine.ordered_options(engine.by_id["q3"], {}, None)
        assert [o.value for o in options] == ["Male", "Female"] and order is None


# --------------------------------------------------------------------------- checking answers


class TestAnswerChecks:
    def check(self, engine, qid, value, other=None):
        q = engine.by_id[qid]
        return clean_answer(q, value, other, engine.options_for(q, {}))

    def test_required(self, engine):
        with pytest.raises(AnswerError, match="Please answer"):
            self.check(engine, "q3", None)

    def test_optional_can_be_empty(self, engine):
        assert self.check(engine, "q9", "").value is None

    def test_choice_must_be_an_option(self, engine):
        with pytest.raises(AnswerError):
            self.check(engine, "q3", "Robot")

    def test_number_range(self, engine):
        assert self.check(engine, "q2", "25").value == 25
        with pytest.raises(AnswerError, match="from 18 to 60"):
            self.check(engine, "q2", 12)
        with pytest.raises(AnswerError, match="number"):
            self.check(engine, "q2", "twelve")
        with pytest.raises(AnswerError):
            self.check(engine, "q2", True)

    def test_rating_and_nps(self, engine):
        with pytest.raises(AnswerError):
            self.check(engine, "q8", 6)
        with pytest.raises(AnswerError):
            self.check(engine, "q8", 2.5)
        assert self.check(engine, "q10", 0).value == 0
        with pytest.raises(AnswerError):
            self.check(engine, "q10", 11)

    def test_multi_max_and_exclusive(self, engine):
        with pytest.raises(AnswerError, match="at most 3"):
            self.check(engine, "q6", ["Samsung", "Apple", "Xiaomi", "Vivo"])
        with pytest.raises(AnswerError, match="can't be combined"):
            self.check(engine, "q14", ["Shop visit", "None of these"])
        assert self.check(engine, "q14", ["None of these"]).value == ["None of these"]

    def test_multi_keeps_file_order_and_drops_repeats(self, engine):
        assert self.check(engine, "q6", ["Vivo", "Samsung", "Vivo"]).value == ["Samsung", "Vivo"]

    def test_other_needs_its_text(self, engine):
        with pytest.raises(AnswerError, match="type your answer"):
            self.check(engine, "q6", ["Other (specify)"], other="  ")
        assert self.check(engine, "q6", ["Other (specify)"], other="  Nokia ").other_text == "Nokia"

    def test_minlength(self, engine):
        with pytest.raises(AnswerError, match="at least 10"):
            self.check(engine, "q9", "bad")

    def test_pincode(self, engine):
        assert self.check(engine, "q17", "400 001").value == "400001"
        with pytest.raises(AnswerError, match="pincode"):
            self.check(engine, "q17", "12345")

    def test_matrix_needs_every_row(self, engine):
        with pytest.raises(AnswerError, match="every row"):
            self.check(engine, "q11", {"The battery lasts a full day": "Agree"})
        with pytest.raises(AnswerError):
            self.check(engine, "q11", {**MATRIX, "Made up row": "Agree"})
        assert self.check(engine, "q11", MATRIX).value == MATRIX

    def test_yesno_without_options_offers_yes_and_no(self, engine):
        assert [o.value for o in engine.options_for(engine.by_id["q5"], {})] == ["Yes", "No"]

    def test_info_needs_no_answer(self, engine):
        assert self.check(engine, "q0", "anything").value is None

    @pytest.mark.parametrize("raw, ok", [("9876543210", True), ("+91 98765 43210", True), ("09876543210", True),
                                         ("12345", False), ("5876543210", False)])
    def test_phone_format(self, raw, ok):
        e = engine_of('<question id="q1" type="formatted" format="phone"><text>A</text></question>')
        q = e.by_id["q1"]
        if ok:
            assert clean_answer(q, raw, None, []).value == "9876543210"
        else:
            with pytest.raises(AnswerError):
                clean_answer(q, raw, None, [])

    def test_email_format(self):
        q = engine_of('<question id="q1" type="formatted" format="email"><text>A</text></question>').by_id["q1"]
        assert clean_answer(q, "ravi@example.com", None, []).value == "ravi@example.com"
        with pytest.raises(AnswerError):
            clean_answer(q, "ravi@", None, [])


class TestShowIfOperators:
    def test_multi_contains_not_equal_and_number_compare(self):
        e = engine_of(
            '<question id="q1" type="multi" required><text>A</text><option>Tea</option><option>Coffee</option></question>\n'
            '<question id="q2" type="number" required><text>B</text></question>\n'
            '<question id="q3" type="text" show-if="q1=Coffee AND q2>=18"><text>C</text></question>\n'
            '<question id="q4" type="text" show-if="q1!=Tea"><text>D</text></question>\n'
            '<question id="q5" type="info"><text>End</text></question>'
        )
        adult_coffee = Respondent(e).answer("q1", ["Coffee"]).answer("q2", 30)
        assert adult_coffee.now == "q3"
        tea_teen = Respondent(e).answer("q1", ["Tea"]).answer("q2", 15)
        assert tea_teen.now == "q5"
