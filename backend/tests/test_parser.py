"""Parser tests: the file becomes clean objects with line numbers, and bad input never crashes."""

import random
import string

import pytest

from app.questionnaire import parse_questionnaire


def codes(result):
    return [i.code for i in result.issues]


def find(result, code):
    matches = [i for i in result.issues if i.code == code]
    assert matches, f"expected an issue with code {code!r}, got {codes(result)}"
    return matches[0]


# --------------------------------------------------------------------------- sample file


class TestSampleFile:
    def test_parses_without_any_issue(self, sample_text):
        result = parse_questionnaire(sample_text)
        assert result.issues == []
        assert result.ok

    def test_survey_attributes(self, sample_text):
        survey = parse_questionnaire(sample_text).survey
        assert survey.sid == "smartphone_study"
        assert survey.title == "Smartphone Usage Study"
        assert survey.target == "200"
        assert survey.line == 1

    def test_all_questions_in_file_order(self, sample_text):
        survey = parse_questionnaire(sample_text).survey
        assert [q.qid for q in survey.questions] == [f"q{n}" for n in range(18)]

    def test_question_types(self, sample_text):
        types = {q.qid: q.type for q in parse_questionnaire(sample_text).survey.questions}
        assert types["q0"] == "info"
        assert types["q1"] == "consent"
        assert types["q4"] == "dropdown"
        assert types["q10"] == "nps"
        assert types["q11"] == "matrix"
        assert types["q17"] == "formatted"

    def test_question_lines_and_text(self, sample_text):
        qs = {q.qid: q for q in parse_questionnaire(sample_text).survey.questions}
        assert qs["q4"].line == 20
        assert qs["q4"].text == "Which city do you live in?"
        assert qs["q4"].text_line == 21
        assert qs["q8"].text == "How happy are you with your [q7] phone?"

    def test_bare_required_attribute(self, sample_text):
        qs = {q.qid: q for q in parse_questionnaire(sample_text).survey.questions}
        assert qs["q1"].required is True
        assert qs["q0"].required is False
        assert qs["q9"].required is False

    def test_rules_are_kept_as_written(self, sample_text):
        qs = {q.qid: q for q in parse_questionnaire(sample_text).survey.questions}
        assert qs["q4"].attrs.get("terminate-on") == "Other city"
        assert qs["q4"].attrs.get("reason") == "City not in scope"
        assert qs["q7"].attrs.get("options-from") == "q6"
        assert qs["q9"].attrs.get("show-if") == "q8=1 OR q8=2"
        assert qs["q15"].attrs.get("show-if") == "q12=Yes AND q4=Mumbai"
        assert qs["q8"].attrs.get("low-label") == "Very unhappy"
        assert qs["q2"].attrs.get("min") == "18"
        assert qs["q17"].attrs.get("format") == "pincode"

    def test_options_with_flags(self, sample_text):
        qs = {q.qid: q for q in parse_questionnaire(sample_text).survey.questions}
        brands = qs["q6"].options
        assert [o.label for o in brands][:3] == ["Samsung", "Apple", "Xiaomi"]
        assert len(brands) == 7
        other = brands[-1]
        assert other.label == "Other (specify)"
        assert other.fixed and other.is_other and not other.exclusive
        assert other.line == 34
        assert qs["q6"].shuffle is True

        none = qs["q14"].options[-1]
        assert none.label == "None of these"
        assert none.exclusive and none.fixed and none.line == 76

    def test_several_options_on_one_line(self, sample_text):
        qs = {q.qid: q for q in parse_questionnaire(sample_text).survey.questions}
        assert [(o.label, o.line) for o in qs["q3"].options] == [("Male", 17), ("Female", 17)]

    def test_skip_to_on_option(self, sample_text):
        qs = {q.qid: q for q in parse_questionnaire(sample_text).survey.questions}
        yes, no = qs["q12"].options
        assert yes.skip_to is None
        assert no.label == "No" and no.skip_to == "q16"

    def test_matrix_rows_and_scale(self, sample_text):
        qs = {q.qid: q for q in parse_questionnaire(sample_text).survey.questions}
        matrix = qs["q11"]
        assert [r.label for r in matrix.rows][0] == "The battery lasts a full day"
        assert len(matrix.rows) == 4
        assert matrix.rows[3].line == 58
        assert [o.label for o in matrix.options] == [
            "Strongly agree", "Agree", "Neutral", "Disagree", "Strongly disagree",
        ]

    def test_quotas(self, sample_text):
        quotas = parse_questionnaire(sample_text).survey.quotas
        assert [(q.question, q.value, q.target, q.line) for q in quotas] == [
            ("q3", "Male", "100", 92),
            ("q3", "Female", "100", 93),
            ("q4", "Mumbai", "80", 94),
        ]


# --------------------------------------------------------------------------- broken file


class TestBrokenFile:
    """The broken file has content mistakes, not structure mistakes.
    The parser must read all of it so the validator (step 2) can report every mistake."""

    def test_structure_is_readable(self, broken_text):
        result = parse_questionnaire(broken_text)
        assert result.issues == []
        assert result.survey.sid == "snack_study"
        assert len(result.survey.questions) == 12

    def test_question_without_id_is_kept(self, broken_text):
        q = parse_questionnaire(broken_text).survey.questions[3]
        assert q.qid is None
        assert q.line == 16
        assert q.type == "dropdown"

    def test_duplicate_ids_are_both_kept(self, broken_text):
        qs = parse_questionnaire(broken_text).survey.questions
        assert [q.line for q in qs if q.qid == "q6"] == [25, 35]

    def test_apostrophe_in_option(self, broken_text):
        q6 = parse_questionnaire(broken_text).survey.questions[5]
        assert "Haldiram's" in [o.label for o in q6.options]


# --------------------------------------------------------------------------- bad input


class TestBadInput:
    def test_empty_file(self):
        result = parse_questionnaire("   \n\n ")
        assert result.survey is None
        assert find(result, "empty_file").line == 1

    def test_no_survey_tag(self):
        result = parse_questionnaire("hello, this is not a questionnaire")
        assert result.survey is None
        assert "no_survey" in codes(result)

    def test_question_never_closed_is_reported_and_next_question_still_read(self):
        text = (
            '<survey id="s" title="S" target="10">\n'
            '<question id="q1" type="text">\n'
            "  <text>First?</text>\n"
            '<question id="q2" type="text">\n'
            "  <text>Second?</text>\n"
            "</question>\n"
            "</survey>\n"
        )
        result = parse_questionnaire(text)
        issue = find(result, "unclosed_tag")
        assert issue.line == 2
        assert [q.qid for q in result.survey.questions] == ["q1", "q2"]
        assert result.survey.questions[0].text == "First?"

    def test_missing_closing_survey(self):
        result = parse_questionnaire('<survey id="s">\n<question id="q1" type="info"><text>Hi</text></question>\n')
        assert find(result, "unclosed_tag").line == 1
        assert result.survey.questions[0].qid == "q1"

    def test_closing_tag_without_opening(self):
        result = parse_questionnaire('<survey id="s">\n</option>\n</survey>')
        assert find(result, "stray_closing_tag").line == 2

    def test_unknown_tag_suggests_a_fix(self):
        result = parse_questionnaire(
            '<survey id="s">\n<questoin id="q1" type="text"><text>Hi</text></questoin>\n</survey>'
        )
        issue = find(result, "unknown_tag")
        assert issue.line == 2
        assert "question" in issue.message

    def test_option_outside_question(self):
        result = parse_questionnaire('<survey id="s">\n<option>Lost</option>\n</survey>')
        assert find(result, "misplaced_tag").line == 2

    def test_text_outside_any_tag(self):
        result = parse_questionnaire('<survey id="s">\nsome loose words\n</survey>')
        assert find(result, "stray_text").line == 2

    def test_content_after_survey_is_reported(self):
        result = parse_questionnaire('<survey id="s"></survey>\n<question id="q9" type="text"></question>')
        assert find(result, "misplaced_tag").line == 2

    def test_second_survey_is_reported(self):
        result = parse_questionnaire('<survey id="a"></survey>\n<survey id="b"></survey>')
        assert find(result, "second_survey").line == 2
        assert result.survey.sid == "a"

    def test_duplicate_attribute(self):
        result = parse_questionnaire('<survey id="s">\n<question id="q1" id="q2" type="text"></question>\n</survey>')
        assert find(result, "duplicate_attribute").line == 2

    def test_tag_without_closing_bracket(self):
        result = parse_questionnaire('<survey id="s">\n<question id="q1" type="text"\n<text>Hi</text>\n</survey>')
        assert find(result, "broken_tag").line == 2

    def test_quote_not_closed(self):
        result = parse_questionnaire('<survey id="s">\n<question id="q1 type="text">\n</question>\n</survey>')
        assert "quote_not_closed" in codes(result) or "broken_attribute" in codes(result)

    def test_two_text_tags(self):
        result = parse_questionnaire(
            '<survey id="s">\n<question id="q1" type="text">\n<text>A</text>\n<text>B</text>\n</question>\n</survey>'
        )
        assert find(result, "duplicate_text").line == 4


# --------------------------------------------------------------------------- tolerant reading


class TestTolerantReading:
    def test_less_than_sign_inside_text(self):
        result = parse_questionnaire(
            '<survey id="s">\n<question id="q1" type="yesno"><text>Is your age < 18?</text></question>\n</survey>'
        )
        assert result.issues == []
        assert result.survey.questions[0].text == "Is your age < 18?"

    def test_attributes_across_lines_remember_their_line(self):
        text = '<survey id="s">\n<question id="q1"\n   type="text"\n   required>\n<text>Hi</text></question>\n</survey>'
        q = parse_questionnaire(text).survey.questions[0]
        assert q.line == 2
        assert q.attrs.line_of("type", 0) == 3
        assert q.required

    def test_unquoted_and_single_quoted_values(self):
        q = parse_questionnaire("<survey id=s><question id=q1 type='text'><text>Hi</text></question></survey>").survey.questions[0]
        assert (q.qid, q.type) == ("q1", "text")

    def test_entities_and_whitespace_in_text(self):
        q = parse_questionnaire(
            '<survey id="s"><question id="q1" type="text"><text>\n  Fish   &amp; chips\n  today?  </text></question></survey>'
        ).survey.questions[0]
        assert q.text == "Fish & chips today?"

    def test_windows_line_endings_and_bom(self):
        text = '﻿<survey id="s">\r\n<question id="q1" type="text">\r\n<text>Hi</text>\r\n</question>\r\n</survey>\r\n'
        result = parse_questionnaire(text)
        assert result.issues == []
        assert result.survey.questions[0].line == 2

    def test_tag_names_are_case_insensitive(self):
        result = parse_questionnaire('<Survey id="s"><QUESTION id="q1" type="text"><Text>Hi</Text></QUESTION></Survey>')
        assert result.issues == []
        assert result.survey.questions[0].text == "Hi"

    def test_comments_are_ignored(self):
        result = parse_questionnaire('<survey id="s">\n<!-- draft note -->\n</survey>')
        assert result.issues == []

    def test_self_closing_quota_and_open_close_quota(self):
        result = parse_questionnaire(
            '<survey id="s">\n<quota question="q1" value="A" target="5"/>\n<quota question="q1" value="B" target="5"></quota>\n</survey>'
        )
        assert result.issues == []
        assert [q.value for q in result.survey.quotas] == ["A", "B"]


# --------------------------------------------------------------------------- never crash


@pytest.mark.parametrize("seed", range(200))
def test_random_garbage_never_crashes(seed, sample_text):
    rng = random.Random(seed)
    # Mix pure noise with damaged copies of the real file.
    if seed % 2:
        alphabet = string.printable + "<>/=\"'"
        text = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 400)))
    else:
        chars = list(sample_text)
        for _ in range(rng.randint(1, 40)):
            chars[rng.randrange(len(chars))] = rng.choice("<>/=\"' \nqx")
        text = "".join(chars)
    result = parse_questionnaire(text)  # must not raise
    for issue in result.issues:
        assert issue.line >= 1
        assert issue.message
