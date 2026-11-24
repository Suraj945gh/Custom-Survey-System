"""Dashboard numbers and the standard export (the brief's table)."""

import csv
import io
from datetime import timedelta

import pytest
from openpyxl import load_workbook

from app.services import surveys as survey_service
from app.tables import Response, Survey
from tests.test_api_respond import FULL_PATH, MATRIX, Person, make_live, response_of

Q6 = "Q6. Which smartphone brands have you used in the last 3 years? (pick up to 3)"
Q11 = "Q11. How much do you agree with each statement about your phone?"


@pytest.fixture
def filled(client, db, sample_text, researcher, admin):
    """One completed, one terminated (two reasons), one still in progress, one test run."""
    survey = make_live(db, sample_text, researcher, admin)
    Person(client, number=1).walk(FULL_PATH)
    out = Person(client, number=2)
    out.walk(FULL_PATH[:4])
    out.answer("q4", "Other city")
    out.answer("q5", "No")
    Person(client, number=3).walk(FULL_PATH[:7])  # stopped at q7
    return survey


def export_csv(client, headers, survey_id):
    r = client.get(f"/api/surveys/{survey_id}/export?format=csv", headers=headers)
    assert r.status_code == 200
    assert r.headers["content-disposition"].startswith('attachment; filename="smartphone_study_completes_')
    return list(csv.reader(io.StringIO(r.content.decode("utf-8-sig"))))


class TestExport:
    def test_headers_follow_the_standard_format(self, client, researcher_headers, filled):
        header = export_csv(client, researcher_headers, filled.id)[0]
        assert header[:4] == ["Respondent ID", "Version", "Completed at", "Quality flags"]
        assert header[4] == "Q1. Do you agree to take part in this survey?"
        assert not any(h.startswith("Q0.") for h in header)  # info screens have no answer
        assert f"{Q6} - Samsung" in header and f"{Q6} - Other" in header  # one column per option
        assert f"{Q11} - The battery lasts a full day" in header  # one column per matrix row
        assert "Q7. Which of these brands do you use now?" in header

    def test_values(self, client, researcher_headers, filled):
        header, *rows = export_csv(client, researcher_headers, filled.id)
        assert len(rows) == 1  # only completes; terminated, in-progress and test runs are left out
        row = dict(zip(header, rows[0]))
        assert row["Version"] == "1"
        assert row["Q3. What is your gender?"] == "Male"
        assert row[f"{Q6} - Samsung"] == "Samsung"
        assert row[f"{Q6} - Apple"] == ""  # not picked -> blank
        assert row[f"{Q6} - Other"] == "Other-Nokia"  # typed text inside the Other column
        assert row["Q7. Which of these brands do you use now?"] == "Nokia"
        assert row[f"{Q11} - The battery lasts a full day"] == "Agree"
        assert row["Q13. What is your budget for the new phone (in rupees)?"] == "30000"
        assert row["Q9. What makes you unhappy with your [q7] phone?"] == ""  # hidden for this person

    def test_excel_has_the_same_table(self, client, researcher_headers, filled):
        r = client.get(f"/api/surveys/{filled.id}/export?format=xlsx", headers=researcher_headers)
        sheet = load_workbook(io.BytesIO(r.content)).active
        rows = list(sheet.iter_rows(values_only=True))
        assert rows[0][:4] == ("Respondent ID", "Version", "Completed at", "Quality flags")
        assert rows[1][1] == 1 and len(rows) == 2

    def test_new_version_shows_in_the_version_column(self, client, db, researcher_headers, filled, sample_text,
                                                     researcher, admin):
        v2 = sample_text.replace("What is your name?", "What is your full name?")
        survey_service.save_draft(db, v2, researcher, survey=db.get(Survey, filled.id))
        survey_service.approve(db, db.get(Survey, filled.id), admin)
        Person(client, number=4).walk(FULL_PATH)
        header, *rows = export_csv(client, researcher_headers, filled.id)
        assert [r[1] for r in rows] == ["1", "2"]
        assert "Q16. What is your full name?" in header  # headers use the newest wording
        assert dict(zip(header, rows[0]))["Q16. What is your full name?"] == "Ravi"  # v1 answer, same question id

    def test_export_needs_login_and_a_known_format(self, client, researcher_headers, filled):
        assert client.get(f"/api/surveys/{filled.id}/export").status_code == 401
        assert client.get(f"/api/surveys/{filled.id}/export?format=pdf", headers=researcher_headers).status_code == 422


class TestDashboard:
    def test_counts_quotas_and_reasons(self, client, researcher_headers, filled):
        d = client.get(f"/api/surveys/{filled.id}/dashboard", headers=researcher_headers).json()
        assert (d["started"], d["completed"], d["terminated"], d["in_progress"]) == (3, 1, 1, 1)
        assert d["target"] == 200 and d["progress"] == 0  # 1 of 200 rounds to 0 %
        male = next(q for q in d["quotas"] if q["value"] == "Male")
        assert (male["target"], male["done"], male["left"], male["full"]) == (100, 1, 99, False)
        assert d["reasons"] == [
            {"reason": "q4: City not in scope", "count": 1},
            {"reason": "q5: Not a smartphone user", "count": 1},
        ]
        assert d["drop_off"] == [{"question": "q6", "count": 1}]

    def test_test_runs_are_not_counted(self, client, researcher_headers, filled):
        run = client.post(f"/api/surveys/{filled.id}/test-runs", json={"use_draft": False}, headers=researcher_headers)
        Person(client, token=run.json()["token"]).walk(FULL_PATH)
        d = client.get(f"/api/surveys/{filled.id}/dashboard", headers=researcher_headers).json()
        assert d["completed"] == 1 and d["test_runs"] == 1

    def test_survey_list_shows_completes(self, client, researcher_headers, filled):
        listed = client.get("/api/surveys", headers=researcher_headers).json()
        assert listed[0]["completed"] == 1


def took(db, token, minutes):
    """Pretend this person started `minutes` before they finished."""
    r = response_of(db, token)
    r.started_at = r.ended_at - timedelta(minutes=minutes)
    db.commit()


def path_with_matrix(matrix):
    return [step if step[0] != "q11" else ("q11", matrix) for step in FULL_PATH]


class TestQualityFlags:
    """Bonus: speeders and straight-lining are flagged, never deleted."""

    def test_a_normal_complete_is_not_flagged(self, client, db, researcher_headers, filled):
        took(db, db.query(Response).filter_by(status="completed").one().token, 6)
        d = client.get(f"/api/surveys/{filled.id}/dashboard", headers=researcher_headers).json()
        assert d["quality"] == {"checked": 1, "speeders": 0, "straight_liners": 0, "flagged": []}
        header, row = export_csv(client, researcher_headers, filled.id)
        assert dict(zip(header, row))["Quality flags"] == ""

    def test_speeder_under_two_seconds_per_answer(self, client, db, researcher_headers, filled):
        # 17 answers in 20 seconds: nobody can read that fast
        r = db.query(Response).filter_by(status="completed").one()
        r.started_at = r.ended_at - timedelta(seconds=20)
        db.commit()
        d = client.get(f"/api/surveys/{filled.id}/dashboard", headers=researcher_headers).json()
        assert d["quality"]["speeders"] == 1
        assert d["quality"]["flagged"][0]["flags"] == ["Speeder"]
        assert d["quality"]["flagged"][0]["seconds"] == 20

    def test_speeder_against_the_median(self, client, db, researcher_headers, filled):
        db.query(Response).filter_by(status="completed").one().started_at -= timedelta(minutes=9)
        db.commit()
        for n in range(10, 15):  # five more completes, about 9 minutes each, one in 2 minutes
            person = Person(client, number=n)
            person.walk(FULL_PATH)
            took(db, person.token, 2 if n == 14 else 9)
        d = client.get(f"/api/surveys/{filled.id}/dashboard", headers=researcher_headers).json()
        assert d["quality"]["checked"] == 6 and d["quality"]["speeders"] == 1
        assert d["quality"]["flagged"][0]["seconds"] == 120

    def test_straight_lining(self, client, db, researcher_headers, filled):
        same = {row: "Strongly agree" for row in MATRIX}
        person = Person(client, number=20)
        person.walk(path_with_matrix(same))
        took(db, person.token, 7)
        took(db, db.query(Response).filter_by(status="completed").first().token, 7)
        d = client.get(f"/api/surveys/{filled.id}/dashboard", headers=researcher_headers).json()
        assert d["quality"]["straight_liners"] == 1 and d["quality"]["speeders"] == 0
        assert d["quality"]["flagged"][0]["flags"] == ["Straight-lining (q11)"]
        header, *rows = export_csv(client, researcher_headers, filled.id)
        flags = [dict(zip(header, row))["Quality flags"] for row in rows]
        assert sorted(flags) == ["", "Straight-lining (q11)"]
        assert len(rows) == 2  # flagged responses are kept
