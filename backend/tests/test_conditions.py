"""show-if rule reader: text -> small tree, with readable errors."""

import pytest

from app.questionnaire.conditions import AllOf, AnyOf, Compare, ConditionError, comparisons, parse_condition


def test_single_test():
    assert parse_condition("q2=Yes") == Compare("q2", "=", "Yes")


def test_spaces_around_operator_and_in_value():
    assert parse_condition("  q4 = Other city ") == Compare("q4", "=", "Other city")


def test_and():
    assert parse_condition("q12=Yes AND q4=Mumbai") == AllOf((Compare("q12", "=", "Yes"), Compare("q4", "=", "Mumbai")))


def test_or_with_rating_values():
    assert parse_condition("q8=1 OR q8=2") == AnyOf((Compare("q8", "=", "1"), Compare("q8", "=", "2")))


def test_and_binds_tighter_than_or():
    tree = parse_condition("q1=A OR q2=B AND q3=C")
    assert tree == AnyOf((Compare("q1", "=", "A"), AllOf((Compare("q2", "=", "B"), Compare("q3", "=", "C")))))


def test_brackets_change_the_order():
    tree = parse_condition("(q1=A OR q2=B) AND q3=C")
    assert tree == AllOf((AnyOf((Compare("q1", "=", "A"), Compare("q2", "=", "B"))), Compare("q3", "=", "C")))


@pytest.mark.parametrize("op", ["!=", ">=", "<=", ">", "<"])
def test_other_operators(op):
    assert parse_condition(f"q8{op}3") == Compare("q8", op, "3")


def test_quoted_value_may_contain_brackets():
    assert parse_condition("q6='Other (specify)' OR q6=Apple") == AnyOf(
        (Compare("q6", "=", "Other (specify)"), Compare("q6", "=", "Apple"))
    )


def test_lower_case_words_inside_a_value_are_fine():
    assert parse_condition("q5=Salt and pepper") == Compare("q5", "=", "Salt and pepper")


def test_comparisons_lists_every_test():
    tree = parse_condition("(q1=A OR q2=B) AND q3=C")
    assert [c.qid for c in comparisons(tree)] == ["q1", "q2", "q3"]


@pytest.mark.parametrize(
    "text, words",
    [
        ("", "empty"),
        ("   ", "empty"),
        ("q2=", "missing a value"),
        ("q2=Yes AND", "ends too early"),
        ("(q2=Yes", "never closed"),
        ("q2=Yes)", "without a matching"),
        ("q2 Yes", "needs a comparison"),
        ("q2=Yes and q3=No", "capital"),
        ("q2=Yes q3=No", "AND or OR"),
        ("AND q2=Yes", "Unexpected"),
        ("=Yes", "Could not understand"),
    ],
)
def test_bad_rules_give_a_readable_reason(text, words):
    with pytest.raises(ConditionError) as exc:
        parse_condition(text)
    assert words in str(exc.value)
