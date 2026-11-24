"""Respondents through the API: join, answer, back, resume, end screens, many surveys at once."""

from datetime import timedelta

import pytest
from sqlalchemy import select

from app.db import utcnow
from app.services import respond
from app.services import surveys as survey_service
from app.tables import Response, Survey

MATRIX = {
    "The battery lasts a full day": "Agree",
    "The camera takes good photos": "Agree",
    "It works smoothly without lag": "Neutral",
    "It was good value for money": "Agree",
}
FULL_PATH = [
    ("q0", None), ("q1", "Yes"), ("q2", 30), ("q3", "Male"), ("q4", "Mumbai"), ("q5", "Yes"),
    ("q6", ["Samsung", "Other (specify)"], "Nokia"), ("q7", "Nokia"), ("q8", 4), ("q10", 9), ("q11", MATRIX),
    ("q12", "Yes"), ("q13", 30000), ("q14", ["YouTube reviews"]), ("q15", "Yes"), ("q16", "Ravi"), ("q17", "400001"),
]
TINY = """<survey id="tiny" title="Tiny Study" target="2">
<question id="q1" type="single" required><text>Gender?</text><option>Male</option><option>Female</option></question>
<question id="q2" type="text"><text>Name?</text></question>
<quota question="q1" value="Male" target="1"/>
</survey>"""


def phone(n: int) -> str:
    return f"98765{n:05d}"


def make_live(db, text, researcher, admin) -> Survey:
    survey, _ = survey_service.save_draft(db, text, researcher)
    survey_service.approve(db, survey, admin)
    return survey_service.go_live(db, survey)


@pytest.fixture
def live(db, sample_text, researcher, admin):
    return make_live(db, sample_text, researcher, admin)


class Person:
    """A respondent with a phone, using the public API."""

    def __init__(self, client, slug="smartphone_study", number=1, token=None):
        self.client = client
        if token is None:
            r = client.post(f"/api/public/surveys/{slug}/join", json={"phone": phone(number)})
            assert r.status_code == 200, r.json()
            token = r.json()["token"]
        self.token = token

    def screen(self):
        return self.client.get(f"/api/public/r/{self.token}").json()

    def answer(self, qid, value=None, other=None, expect=200):
        r = self.client.post(f"/api/public/r/{self.token}/answers", json={"qid": qid, "value": value, "other_text": other})
        assert r.status_code == expect, r.json()
        return r.json()

    def walk(self, steps):
        screen = None
        for step in steps:
            screen = self.answer(*step)
        return screen


def response_of(db, token) -> Response:
    db.expire_all()
    return db.scalar(select(Response).where(Response.token == token))


# --------------------------------------------------------------------------- joining


class TestJoin:
    def test_public_info(self, client, live):
        r = client.get("/api/public/surveys/smartphone_study").json()
        assert r == {"slug": "smartphone_study", "title": "Smartphone Usage Study", "open": True, "message": None}

    def test_unknown_or_never_live_survey_is_hidden(self, client, db, researcher, broken_text):
        survey_service.save_draft(db, broken_text, researcher)
        assert client.get("/api/public/surveys/nope").status_code == 404
        assert client.get("/api/public/surveys/snack_study").status_code == 404

    def test_same_phone_gets_the_same_link(self, client, live):
        first = client.post("/api/public/surveys/smartphone_study/join", json={"phone": "9876500001"}).json()
        again = client.post("/api/public/surveys/smartphone_study/join", json={"phone": "+91 98765 00001"}).json()
        assert first["resumed"] is False and again["resumed"] is True
        assert first["token"] == again["token"]

    def test_bad_phone(self, client, live):
        r = client.post("/api/public/surveys/smartphone_study/join", json={"phone": "12345"})
        assert r.status_code == 422 and "10-digit" in r.json()["detail"]

    def test_response_starts_on_the_current_version(self, client, db, live):
        person = Person(client)
        assert response_of(db, person.token).version.version_no == 1


# --------------------------------------------------------------------------- answering


class TestAnswering:
    def test_first_screen(self, client, live):
        screen = Person(client).screen()
        assert screen["kind"] == "question" and screen["question"]["qid"] == "q0"
        assert screen["previous_qid"] is None and screen["progress"] == 0

    def test_full_walk_through_completes(self, client, db, live):
        person = Person(client)
        end = person.walk(FULL_PATH)
        assert end["kind"] == "end" and end["end"] == "completed"
        assert response_of(db, person.token).status == "completed"
        assert person.screen()["end"] == "already_completed"  # reopening the link later

    def test_piping_and_other_text_reach_the_screen(self, client, live):
        person = Person(client)
        person.walk(FULL_PATH[:6])
        q7 = person.answer("q6", ["Samsung", "Other (specify)"], "Nokia")
        assert [o["label"] for o in q7["question"]["options"]] == ["Samsung", "Nokia"]
        q8 = person.answer("q7", "Nokia")
        assert q8["question"]["text"] == "How happy are you with your Nokia phone?"
        assert q8["question"]["settings"] == {"min": 1, "max": 5, "low_label": "Very unhappy", "high_label": "Very happy"}

    def test_every_answer_is_saved_at_once_and_resume_works(self, client, db, live):
        person = Person(client)
        person.walk(FULL_PATH[:6])
        assert len(response_of(db, person.token).answers) == 6
        # The phone dies. Later the person opens the same link again on another device:
        later = Person(client, token=person.token).screen()
        assert later["question"]["qid"] == "q6"

    def test_back_shows_the_saved_answer(self, client, live):
        person = Person(client)
        person.walk(FULL_PATH[:6])
        back = client.get(f"/api/public/r/{person.token}/questions/q4").json()
        assert back["answer"] == {"value": "Mumbai", "other_text": None}
        assert back["previous_qid"] == "q3"
        # after re-answering q4 the next screen is q5 (already answered, shown with its answer)
        nxt = person.answer("q4", "Pune")
        assert nxt["question"]["qid"] == "q5" and nxt["answer"]["value"] == "Yes"

    def test_cannot_jump_ahead(self, client, live):
        person = Person(client)
        assert client.get(f"/api/public/r/{person.token}/questions/q10").status_code == 409
        person.answer("q10", 5, expect=409)

    def test_invalid_answer_is_explained(self, client, live):
        person = Person(client)
        person.walk(FULL_PATH[:2])
        r = client.post(f"/api/public/r/{person.token}/answers", json={"qid": "q2", "value": 12})
        assert r.status_code == 422
        assert r.json() == {"detail": "Please enter a number from 18 to 60.", "code": "invalid_answer"}

    def test_unknown_link(self, client, live):
        r = client.get("/api/public/r/not-a-real-token")
        assert r.status_code == 404 and "not valid" in r.json()["detail"]

    def test_shuffled_order_is_kept(self, client, db, live):
        person = Person(client)
        first = person.walk(FULL_PATH[:6])["question"]["options"]
        again = person.screen()["question"]["options"]
        assert first == again
        assert first[-1]["value"] == "Other (specify)"  # fixed option stays last
        assert "q6" in response_of(db, person.token).option_orders

    def test_q12_no_skips_to_q16_through_the_api(self, client, live):
        person = Person(client)
        person.walk(FULL_PATH[:11])
        assert person.answer("q12", "No")["question"]["qid"] == "q16"


class TestEnding:
    def test_two_failed_rules_end_it_with_both_reasons(self, client, db, live):
        person = Person(client)
        person.walk(FULL_PATH[:4])
        person.answer("q4", "Other city")
        end = person.answer("q5", "No")
        assert end["end"] == "not_eligible"
        assert "reasons" not in end or end["reasons"] is None  # real respondents don't see the reasons
        saved = response_of(db, person.token)
        assert saved.status == "terminated"
        assert saved.end_reasons == "q4: City not in scope | q5: Not a smartphone user"
        assert person.screen()["end"] == "not_eligible"

    def test_consent_no(self, client, db, live):
        person = Person(client)
        person.answer("q0")
        assert person.answer("q1", "No")["end"] == "not_eligible"
        assert response_of(db, person.token).end_reasons == "q1: Did not give consent"

    def test_full_quota_ends_later_people(self, client, db, researcher, admin):
        make_live(db, TINY, researcher, admin)
        first = Person(client, "tiny", 1)
        assert first.walk([("q1", "Male"), ("q2", "A")])["end"] == "completed"
        second = Person(client, "tiny", 2)
        assert second.answer("q1", "Male")["end"] == "not_eligible"
        assert response_of(db, second.token).end_reasons == "q1: Quota full (Male)"

    def test_last_quota_place_is_checked_again_when_finishing(self, client, db, researcher, admin):
        make_live(db, TINY, researcher, admin)
        a, b = Person(client, "tiny", 1), Person(client, "tiny", 2)
        a.answer("q1", "Male")
        b.answer("q1", "Male")  # both passed screening while the quota was still open
        assert a.answer("q2", "A")["end"] == "completed"
        assert b.answer("q2", "B")["end"] == "not_eligible"  # final check at completion
        assert response_of(db, b.token).end_reasons == "q1: Quota full (Male)"

    def test_target_reached_closes_the_survey(self, client, db, researcher, admin):
        make_live(db, TINY, researcher, admin)
        waiting = Person(client, "tiny", 9)
        waiting.answer("q1", "Female")  # halfway
        Person(client, "tiny", 1).walk([("q1", "Male"), ("q2", "A")])
        Person(client, "tiny", 2).walk([("q1", "Female"), ("q2", "B")])
        assert client.get("/api/public/surveys/tiny").json()["open"] is False
        closed = waiting.screen()
        assert closed["end"] == "closed" and "all the responses we needed" in closed["message"]
        assert response_of(db, waiting.token).status == "in_progress"  # partial answers kept, not counted
        r = client.post("/api/public/surveys/tiny/join", json={"phone": phone(5)})
        assert r.status_code == 409 and r.json()["code"] == "closed"


class TestManySurveys:
    def test_closed_by_team_mid_response(self, client, db, live):
        person = Person(client)
        person.walk(FULL_PATH[:3])
        survey_service.close(db, db.get(Survey, live.id))
        screen = person.screen()
        assert screen["end"] == "closed" and screen["message"] == "The research team has closed this survey."
        person.answer("q3", "Male")  # submitting also just shows the closed screen
        assert len(response_of(db, person.token).answers) == 3

    def test_in_progress_stays_on_v1_when_v2_is_approved(self, client, db, live, sample_text, researcher, admin):
        early = Person(client, number=1)
        early.walk(FULL_PATH[:15])
        v2_text = sample_text.replace("What is your name?", "What is your full name?")
        survey_service.save_draft(db, v2_text, researcher, survey=db.get(Survey, live.id))
        survey_service.approve(db, db.get(Survey, live.id), admin)

        assert early.screen()["question"]["text"] == "What is your name?"  # still v1
        late = Person(client, number=2)
        late.walk(FULL_PATH[:15])
        assert late.screen()["question"]["text"] == "What is your full name?"  # v2
        assert response_of(db, late.token).version.version_no == 2

    def test_cool_off_after_completing_any_survey(self, client, db, live, researcher, admin):
        make_live(db, TINY, researcher, admin)
        Person(client, number=1).walk(FULL_PATH)  # completed the smartphone study
        r = client.post("/api/public/surveys/tiny/join", json={"phone": phone(1)})
        assert r.status_code == 403
        assert r.json()["code"] == "cool_off" and "eligible_from" in r.json()

    def test_cool_off_ends_after_90_days(self, client, db, live, researcher, admin):
        make_live(db, TINY, researcher, admin)
        done = Person(client, number=1)
        done.walk(FULL_PATH)
        saved = response_of(db, done.token)
        saved.ended_at = utcnow() - timedelta(days=91)
        db.commit()
        assert client.post("/api/public/surveys/tiny/join", json={"phone": phone(1)}).status_code == 200

    def test_terminated_people_are_not_cooled_off(self, client, db, live, researcher, admin):
        make_live(db, TINY, researcher, admin)
        person = Person(client, number=1)
        person.answer("q0")
        person.answer("q1", "No")
        assert client.post("/api/public/surveys/tiny/join", json={"phone": phone(1)}).status_code == 200


class TestTestMode:
    def test_test_run_on_a_draft_is_never_counted(self, client, db, researcher_headers, sample_text):
        survey = client.post("/api/surveys", json={"text": sample_text}, headers=researcher_headers).json()
        run = client.post(f"/api/surveys/{survey['id']}/test-runs", headers=researcher_headers)
        assert run.status_code == 201 and run.json()["is_draft"] is True
        tester = Person(client, token=run.json()["token"])
        assert tester.screen()["is_test"] is True  # works although the survey is not live
        assert tester.walk(FULL_PATH)["end"] == "completed"
        assert respond.completes(db, survey["id"]) == 0

    def test_test_run_shows_the_reasons(self, client, researcher_headers, sample_text):
        survey = client.post("/api/surveys", json={"text": sample_text}, headers=researcher_headers).json()
        tester = Person(client, token=client.post(f"/api/surveys/{survey['id']}/test-runs", headers=researcher_headers).json()["token"])
        tester.walk(FULL_PATH[:4])
        tester.answer("q4", "Other city")
        assert tester.answer("q5", "Yes")["reasons"] == "q4: City not in scope"

    def test_test_run_does_not_fill_quotas(self, client, db, researcher, admin, researcher_headers):
        survey = make_live(db, TINY, researcher, admin)
        token = client.post(f"/api/surveys/{survey.id}/test-runs", json={"use_draft": False}, headers=researcher_headers).json()["token"]
        Person(client, token=token).walk([("q1", "Male"), ("q2", "T")])
        real = Person(client, "tiny", 1)
        assert real.walk([("q1", "Male"), ("q2", "A")])["end"] == "completed"  # the quota place was still free

    def test_draft_with_errors_cannot_be_previewed(self, client, researcher_headers, broken_text):
        survey = client.post("/api/surveys", json={"text": broken_text}, headers=researcher_headers).json()
        r = client.post(f"/api/surveys/{survey['id']}/test-runs", headers=researcher_headers)
        assert r.status_code == 409 and "Fix the errors" in r.json()["detail"]

    def test_test_runs_need_a_login(self, client, live):
        assert client.post(f"/api/surveys/{live.id}/test-runs").status_code == 401
