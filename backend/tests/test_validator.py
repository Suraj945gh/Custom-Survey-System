"""Validator: every content mistake is found, with the right line, and good files stay clean."""

import pytest

from app.questionnaire import check_questionnaire

HEAD = '<survey id="s" title="S" target="100">'


def survey(body: str, head: str = HEAD) -> str:
    """Wrap questions in a survey tag. The body starts on line 2."""
    return f"{head}\n{body}\n</survey>\n"


def errors(text: str) -> list[tuple[int, str]]:
    return [(i.line, i.code) for i in check_questionnaire(text).errors]


def warnings(text: str) -> list[tuple[int, str]]:
    return [(i.line, i.code) for i in check_questionnaire(text).warnings]


def message(text: str, code: str) -> str:
    found = [i.message for i in check_questionnaire(text).issues if i.code == code]
    assert found, f"no issue with code {code}"
    return found[0]


YESNO = '<question id="q1" type="yesno" required><text>Smoke?</text></question>'


# --------------------------------------------------------------------------- the two sample files


class TestSampleFile:
    def test_has_no_errors_and_no_warnings(self, sample_text):
        result = check_questionnaire(sample_text)
        assert result.issues == []
        assert result.ok


class TestBrokenFile:
    """Our acceptance test: all 10 known mistakes, each on its own line, nothing extra."""

    EXPECTED = [
        (11, "unknown_type"),  # 1. type="singel"
        (16, "missing_id"),  # 2. city question has no id
        (21, "unknown_value"),  # 3. terminate-on="Never" on a yes/no question
        (31, "unknown_reference"),  # 4. options-from="q66"
        (35, "duplicate_id"),  # 5. q6 declared twice
        (39, "forward_reference"),  # 6a. show-if uses q10, which comes later
        (39, "unknown_value"),  # 6b. ...and "Yes" is not an answer of q10
        (45, "unknown_reference"),  # 7. skip-to="q20"
        (48, "matrix_no_scale"),  # 8. matrix without scale options
        (57, "unknown_value"),  # 9. quota q3=Others
        (58, "unknown_value"),  # 10. quota q2=Mumbai on a number question
    ]

    def test_reports_exactly_the_known_errors(self, broken_text):
        assert errors(broken_text) == self.EXPECTED

    def test_not_approvable(self, broken_text):
        assert not check_questionnaire(broken_text).ok

    def test_messages_help_to_fix(self, broken_text):
        text = "\n".join(str(i) for i in check_questionnaire(broken_text).issues)
        assert "Did you mean 'single'?" in text
        assert "Did you mean 'q6'?" in text  # q66 -> q6
        assert "first on line 25" in text
        assert "(Yes, No)" in text
        assert "question on line 16" in text  # Mumbai belongs to the city question


# --------------------------------------------------------------------------- survey tag


class TestSurveyTag:
    def test_missing_id_and_target(self):
        text = survey(YESNO, head='<survey title="S">')
        assert (1, "missing_survey_id") in errors(text)
        assert (1, "missing_target") in errors(text)

    @pytest.mark.parametrize("target", ["abc", "0", "-5", "2.5"])
    def test_bad_target(self, target):
        assert (1, "bad_number") in errors(survey(YESNO, head=f'<survey id="s" target="{target}">'))

    def test_missing_title_is_only_a_warning(self):
        text = survey(YESNO, head='<survey id="s" target="10">')
        assert errors(text) == []
        assert (1, "missing_title") in warnings(text)

    def test_no_questions(self):
        assert (1, "no_questions") in errors(survey(""))


# --------------------------------------------------------------------------- ids, type, text


class TestQuestionBasics:
    def test_bad_id(self):
        assert (2, "bad_id") in errors(survey('<question id="1st q" type="yesno"><text>A</text></question>'))

    def test_missing_type(self):
        assert (2, "missing_type") in errors(survey('<question id="q1"><text>A</text></question>'))

    def test_type_is_case_insensitive(self):
        assert errors(survey('<question id="q1" type="YesNo"><text>A</text></question>')) == []

    def test_missing_text(self):
        assert (2, "missing_text") in errors(survey('<question id="q1" type="yesno"></question>'))

    def test_typo_in_attribute_is_an_error(self):
        text = survey('<question id="q1" type="yesno" requried><text>A</text></question>')
        assert (2, "unknown_attribute") in errors(text)
        assert "Did you mean 'required'?" in message(text, "unknown_attribute")

    def test_unrelated_attribute_is_a_warning(self):
        text = survey('<question id="q1" type="yesno" colour="red"><text>A</text></question>')
        assert errors(text) == []
        assert (2, "unknown_attribute") in warnings(text)


# --------------------------------------------------------------------------- options and types


class TestOptionsAndTypes:
    def test_choice_question_needs_options(self):
        assert (2, "no_options") in errors(survey('<question id="q1" type="single"><text>A</text></question>'))

    def test_one_option_is_a_warning(self):
        text = survey('<question id="q1" type="single"><text>A</text>\n<option>Only</option></question>')
        assert errors(text) == []
        assert (3, "few_options") in warnings(text)

    def test_duplicate_and_empty_option(self):
        text = survey(
            '<question id="q1" type="single"><text>A</text>\n<option>Tea</option>\n<option>tea</option>\n<option> </option></question>'
        )
        assert (4, "duplicate_option") in errors(text)
        assert (5, "empty_option") in errors(text)

    def test_yesno_with_three_options(self):
        text = survey('<question id="q1" type="yesno"><text>A</text>\n<option>Yes</option><option>No</option><option>Maybe</option></question>')
        assert (3, "bad_yesno_options") in errors(text)

    def test_matrix_needs_rows(self):
        text = survey('<question id="q1" type="matrix"><text>A</text><option>Agree</option><option>Disagree</option></question>')
        assert (2, "matrix_no_rows") in errors(text)

    def test_options_on_a_text_question_are_ignored(self):
        text = survey('<question id="q1" type="text"><text>A</text>\n<option>X</option></question>')
        assert (3, "options_ignored") in warnings(text)

    def test_rating_min_must_be_below_max(self):
        assert (2, "bad_range") in errors(survey('<question id="q1" type="rating" min="5" max="1"><text>A</text></question>'))

    def test_rating_min_must_be_a_whole_number(self):
        assert (2, "bad_number") in errors(survey('<question id="q1" type="rating" min="one"><text>A</text></question>'))

    def test_number_min_above_max(self):
        assert (2, "bad_range") in errors(survey('<question id="q1" type="number" min="60" max="18"><text>A</text></question>'))

    def test_text_minlength_must_be_a_number(self):
        assert (2, "bad_number") in errors(survey('<question id="q1" type="longtext" minlength="ten"><text>A</text></question>'))

    def test_formatted_needs_a_known_format(self):
        assert (2, "missing_format") in errors(survey('<question id="q1" type="formatted"><text>A</text></question>'))
        text = survey('<question id="q1" type="formatted" format="phon"><text>A</text></question>')
        assert (2, "unknown_format") in errors(text)
        assert "Did you mean 'phone'?" in message(text, "unknown_format")

    def test_multi_max_larger_than_options(self):
        text = survey('<question id="q1" type="multi" max="5"><text>A</text><option>X</option><option>Y</option></question>')
        assert (2, "max_too_big") in warnings(text)

    def test_exclusive_on_single_question(self):
        text = survey('<question id="q1" type="single"><text>A</text><option>X</option>\n<option exclusive="true">None</option></question>')
        assert (3, "misplaced_flag") in warnings(text)


# --------------------------------------------------------------------------- rules pointing at other questions


class TestReferences:
    def test_show_if_on_an_earlier_question_is_fine(self):
        text = survey(YESNO + '\n<question id="q2" type="text" show-if="q1=Yes"><text>Why?</text></question>')
        assert errors(text) == []

    def test_show_if_value_check_ignores_case(self):
        text = survey(YESNO + '\n<question id="q2" type="text" show-if="q1=yes"><text>Why?</text></question>')
        assert errors(text) == []

    def test_show_if_unknown_question(self):
        text = survey(YESNO + '\n<question id="q2" type="text" show-if="q9=Yes"><text>Why?</text></question>')
        assert (3, "unknown_reference") in errors(text)

    def test_show_if_on_itself(self):
        assert (2, "self_reference") in errors(survey('<question id="q1" type="yesno" show-if="q1=Yes"><text>A</text></question>'))

    def test_show_if_that_cannot_be_read(self):
        text = survey(YESNO + '\n<question id="q2" type="text" show-if="q1=Yes AND"><text>Why?</text></question>')
        assert (3, "bad_condition") in errors(text)

    def test_show_if_rating_value_out_of_range(self):
        text = survey(
            '<question id="q1" type="rating" min="1" max="5"><text>A</text></question>\n'
            '<question id="q2" type="text" show-if="q1=7"><text>B</text></question>'
        )
        assert (3, "unknown_value") in errors(text)

    def test_show_if_greater_than_on_a_choice_question(self):
        text = survey(YESNO + '\n<question id="q2" type="text" show-if="q1>Yes"><text>B</text></question>')
        assert (3, "unknown_value") in errors(text)

    def test_show_if_on_a_matrix(self):
        text = survey(
            '<question id="q1" type="matrix"><text>A</text><row>R</row><option>X</option><option>Y</option></question>\n'
            '<question id="q2" type="text" show-if="q1=X"><text>B</text></question>'
        )
        assert (3, "unknown_value") in errors(text)

    def test_skip_to_backwards(self):
        text = survey(
            YESNO + '\n<question id="q2" type="single"><text>B</text>\n<option>X</option><option skip-to="q1">Y</option></question>'
        )
        assert (4, "backward_skip") in errors(text)

    def test_options_from_needs_a_choice_question(self):
        text = survey(
            '<question id="q1" type="text"><text>A</text></question>\n'
            '<question id="q2" type="single" options-from="q1"><text>B</text></question>'
        )
        assert (3, "bad_options_source") in errors(text)

    def test_options_from_on_a_text_question(self):
        text = survey(
            '<question id="q1" type="multi"><text>A</text><option>X</option><option>Y</option></question>\n'
            '<question id="q2" type="text" options-from="q1"><text>B</text></question>'
        )
        assert (3, "misplaced_rule") in errors(text)

    def test_terminate_on_value_of_a_copied_option_is_fine(self):
        text = survey(
            '<question id="q1" type="multi" required><text>A</text><option>X</option><option>Y</option></question>\n'
            '<question id="q2" type="single" required options-from="q1" terminate-on="Y" reason="r"><text>B</text></question>'
        )
        assert errors(text) == []

    def test_terminate_on_without_reason_is_a_warning(self):
        text = survey('<question id="q1" type="yesno" terminate-on="No"><text>A</text></question>')
        assert errors(text) == []
        assert (2, "missing_reason") in warnings(text)


class TestPiping:
    def test_piping_a_later_question(self):
        text = survey(
            '<question id="q1" type="text" required><text>You said [q2]</text></question>\n'
            '<question id="q2" type="text" required><text>B</text></question>'
        )
        assert (2, "forward_reference") in errors(text)

    def test_piping_an_unknown_question(self):
        assert (2, "unknown_reference") in errors(survey('<question id="q1" type="text"><text>You said [q9]</text></question>'))

    def test_plain_words_in_brackets_are_not_piping(self):
        assert errors(survey('<question id="q1" type="text"><text>Your name [optional]</text></question>')) == []

    def test_piping_an_optional_question_is_a_warning(self):
        text = survey(
            '<question id="q1" type="text"><text>A</text></question>\n'
            '<question id="q2" type="text"><text>You said [q1]</text></question>'
        )
        assert errors(text) == []
        assert (3, "may_be_unanswered") in warnings(text)

    def test_piping_a_question_that_a_skip_can_jump_over(self):
        text = survey(
            '<question id="q1" type="yesno" required><text>A</text>\n<option>Yes</option><option skip-to="q3">No</option></question>\n'
            '<question id="q2" type="text" required><text>B</text></question>\n'
            '<question id="q3" type="text" required><text>You said [q2]</text></question>'
        )
        assert (5, "may_be_unanswered") in warnings(text)
        assert "line 3" in message(text, "may_be_unanswered")


# --------------------------------------------------------------------------- quotas


GENDER = '<question id="q1" type="single" required><text>Gender?</text><option>Male</option><option>Female</option></question>'


class TestQuotas:
    def test_valid_quotas(self):
        text = survey(GENDER + '\n<quota question="q1" value="Male" target="50"/>\n<quota question="q1" value="Female" target="50"/>')
        assert check_questionnaire(text).issues == []

    def test_unknown_question(self):
        assert (3, "unknown_reference") in errors(survey(GENDER + '\n<quota question="q9" value="Male" target="50"/>'))

    def test_missing_fields(self):
        assert (3, "quota_missing_field") in errors(survey(GENDER + '\n<quota question="q1" target="50"/>'))

    @pytest.mark.parametrize("target", ["fifty", "0", "-1"])
    def test_bad_target(self, target):
        assert (3, "bad_number") in errors(survey(GENDER + f'\n<quota question="q1" value="Male" target="{target}"/>'))

    def test_duplicate_quota(self):
        text = survey(GENDER + '\n<quota question="q1" value="Male" target="50"/>\n<quota question="q1" value="male" target="40"/>')
        assert (4, "duplicate_quota") in errors(text)

    def test_quota_larger_than_survey_target(self):
        text = survey(GENDER + '\n<quota question="q1" value="Male" target="150"/>')
        assert (3, "quota_over_target") in warnings(text)

    def test_quotas_that_cap_the_survey_below_target(self):
        text = survey(GENDER + '\n<quota question="q1" value="Male" target="30"/>\n<quota question="q1" value="Female" target="30"/>')
        assert (4, "quotas_below_target") in warnings(text)


# --------------------------------------------------------------------------- robustness


def test_structure_and_content_problems_come_together_sorted_by_line():
    text = survey('<question id="q1" type="singel"><text>A</text>\n<questoin>x</questoin></question>')
    lines = [i.line for i in check_questionnaire(text).issues]
    assert lines == sorted(lines)
    codes = {i.code for i in check_questionnaire(text).issues}
    assert {"unknown_type", "unknown_tag"} <= codes


@pytest.mark.parametrize("seed", range(150))
def test_damaged_files_never_crash_the_validator(seed, sample_text, broken_text):
    import random

    rng = random.Random(seed)
    chars = list(sample_text if seed % 2 else broken_text)
    for _ in range(rng.randint(1, 30)):
        chars[rng.randrange(len(chars))] = rng.choice("<>/=\"' \nqx19-")
    result = check_questionnaire("".join(chars))  # must not raise
    assert all(issue.line >= 1 and issue.message for issue in result.issues)
