"""The spec: clean data that is stored when a survey is saved."""

from app.questionnaire import parse_questionnaire
from app.questionnaire.spec import survey_spec


def spec_of(text):
    return survey_spec(parse_questionnaire(text).survey)


def test_sample_survey_header(sample_text):
    spec = spec_of(sample_text)
    assert (spec["id"], spec["title"], spec["target"]) == ("smartphone_study", "Smartphone Usage Study", 200)
    assert len(spec["questions"]) == 18


def test_rules_become_clean_values(sample_text):
    qs = {q["qid"]: q for q in spec_of(sample_text)["questions"]}
    assert qs["q2"]["rules"] == {"min": 18, "max": 60}
    assert qs["q4"]["rules"] == {"terminate_on": "Other city", "reason": "City not in scope"}
    assert qs["q6"]["rules"] == {"shuffle": True, "max": 3}
    assert qs["q8"]["rules"]["low_label"] == "Very unhappy"
    assert qs["q9"]["rules"] == {"show_if": "q8=1 OR q8=2", "minlength": 10}
    assert qs["q17"]["rules"] == {"format": "pincode"}
    assert qs["q0"]["rules"] == {}


def test_flags_become_booleans(sample_text):
    qs = {q["qid"]: q for q in spec_of(sample_text)["questions"]}
    assert qs["q1"]["required"] is True and qs["q0"]["required"] is False
    other = qs["q6"]["options"][-1]
    assert other == {"label": "Other (specify)", "fixed": True, "other": True, "exclusive": False, "skip_to": None}
    assert qs["q12"]["options"][1]["skip_to"] == "q16"


def test_matrix_rows_and_quotas(sample_text):
    spec = spec_of(sample_text)
    q11 = spec["questions"][11]
    assert q11["rows"][0] == "The battery lasts a full day" and len(q11["options"]) == 5
    assert spec["quotas"][2] == {"question": "q4", "value": "Mumbai", "target": 80}


def test_type_is_lower_case_and_title_falls_back_to_id():
    spec = spec_of('<survey id="s" target="5"><question id="q1" type="YesNo"><text>A</text></question></survey>')
    assert spec["title"] == "s"
    assert spec["questions"][0]["type"] == "yesno"
