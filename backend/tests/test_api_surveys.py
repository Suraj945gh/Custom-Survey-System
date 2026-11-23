"""Staff survey flow through the API: check -> draft -> approve (version N) -> live -> closed."""

from datetime import datetime, timedelta, timezone

import pytest

from app.tables import Survey


def upload(client, headers, text, name="survey.txt"):
    return client.post("/api/surveys/upload", files={"file": (name, text.encode(), "text/plain")}, headers=headers)


@pytest.fixture
def sample_survey(client, researcher_headers, sample_text):
    """The sample file uploaded by a researcher: a draft, not approved yet."""
    r = upload(client, researcher_headers, sample_text, "concave_sample_questionnaire.txt")
    assert r.status_code == 201
    return r.json()


@pytest.fixture
def approved_survey(client, admin_headers, sample_survey):
    r = client.post(f"/api/surveys/{sample_survey['id']}/approve", headers=admin_headers)
    assert r.status_code == 200
    return r.json()


def edited(text, old="Smartphone Usage Study", new="Smartphone Usage Study 2026"):
    return text.replace(old, new)


# --------------------------------------------------------------------------- check


class TestCheck:
    def test_check_lists_errors_with_lines(self, client, researcher_headers, broken_text):
        r = client.post("/api/check", json={"text": broken_text}, headers=researcher_headers)
        body = r.json()
        assert r.status_code == 200
        assert body["ok"] is False and body["error_count"] == 11
        assert body["issues"][0] == {
            "line": 11, "severity": "error", "code": "unknown_type",
            "message": "Question q3 has an unknown type 'singel'. Did you mean 'single'?",
        }
        assert body["survey"]["id"] == "snack_study"

    def test_check_sample_is_ok(self, client, researcher_headers, sample_text):
        body = client.post("/api/check", json={"text": sample_text}, headers=researcher_headers).json()
        assert body["ok"] and body["issues"] == []
        assert body["survey"]["questions"] == 18

    def test_check_saves_nothing(self, client, researcher_headers, sample_text):
        client.post("/api/check", json={"text": sample_text}, headers=researcher_headers)
        assert client.get("/api/surveys", headers=researcher_headers).json() == []


# --------------------------------------------------------------------------- drafts


class TestDrafts:
    def test_upload_creates_a_draft_without_version_number(self, sample_survey):
        assert sample_survey["slug"] == "smartphone_study"
        assert sample_survey["status"] == "draft"
        assert sample_survey["current_version_no"] is None
        assert sample_survey["versions"] == []
        assert sample_survey["draft"]["check"]["ok"] is True
        assert sample_survey["draft"]["file_name"] == "concave_sample_questionnaire.txt"
        assert sample_survey["target"] == 200

    def test_paste_text_also_works(self, client, researcher_headers, sample_text):
        r = client.post("/api/surveys", json={"text": sample_text}, headers=researcher_headers)
        assert r.status_code == 201 and r.json()["has_draft"]

    def test_reupload_replaces_the_draft(self, client, researcher_headers, sample_survey, sample_text):
        again = upload(client, researcher_headers, edited(sample_text)).json()
        assert again["id"] == sample_survey["id"]  # same survey, matched by <survey id>
        assert again["draft"]["id"] == sample_survey["draft"]["id"]  # same single draft row
        assert "Smartphone Usage Study 2026" in again["draft"]["text"]
        assert len(client.get("/api/surveys", headers=researcher_headers).json()) == 1

    def test_broken_file_is_saved_as_draft_with_its_errors(self, client, researcher_headers, broken_text):
        body = upload(client, researcher_headers, broken_text).json()
        assert body["draft"]["check"]["error_count"] == 11

    def test_file_without_survey_id_cannot_be_saved(self, client, researcher_headers):
        r = upload(client, researcher_headers, '<survey title="No id"><question id="q1" type="yesno"><text>A</text></question></survey>')
        assert r.status_code == 422
        assert "survey id" in r.json()["detail"]
        assert "issues" in r.json()

    def test_edit_in_app(self, client, researcher_headers, sample_survey, sample_text):
        r = client.put(f"/api/surveys/{sample_survey['id']}/draft", json={"text": edited(sample_text)}, headers=researcher_headers)
        assert r.status_code == 200
        assert "2026" in r.json()["draft"]["text"]

    def test_edit_that_changes_the_survey_id_is_an_error(self, client, researcher_headers, sample_survey, sample_text):
        text = edited(sample_text, 'id="smartphone_study"', 'id="other_study"')
        body = client.put(f"/api/surveys/{sample_survey['id']}/draft", json={"text": text}, headers=researcher_headers).json()
        assert body["draft"]["check"]["issues"][0]["code"] == "survey_id_changed"

    def test_discard_the_only_draft_deletes_the_survey(self, client, researcher_headers, sample_survey):
        assert client.delete(f"/api/surveys/{sample_survey['id']}/draft", headers=researcher_headers).status_code == 204
        assert client.get(f"/api/surveys/{sample_survey['id']}", headers=researcher_headers).status_code == 404

    def test_discard_a_draft_keeps_approved_versions(self, client, researcher_headers, approved_survey, sample_text):
        upload(client, researcher_headers, edited(sample_text))
        client.delete(f"/api/surveys/{approved_survey['id']}/draft", headers=researcher_headers)
        body = client.get(f"/api/surveys/{approved_survey['id']}", headers=researcher_headers).json()
        assert body["draft"] is None and body["current_version_no"] == 1

    def test_unknown_survey(self, client, researcher_headers):
        assert client.get("/api/surveys/999", headers=researcher_headers).status_code == 404


class TestUploadSafety:
    def test_only_txt_files(self, client, researcher_headers, sample_text):
        assert upload(client, researcher_headers, sample_text, "survey.pdf").status_code == 400

    def test_not_text(self, client, researcher_headers):
        r = client.post("/api/surveys/upload", files={"file": ("x.txt", b"\xff\xfe\x81", "text/plain")}, headers=researcher_headers)
        assert r.status_code == 400

    def test_too_big(self, client, researcher_headers):
        big = "<survey id='s'>" + "x" * (600 * 1024)
        assert upload(client, researcher_headers, big).status_code == 413

    def test_empty_file(self, client, researcher_headers):
        assert upload(client, researcher_headers, "").status_code == 422


# --------------------------------------------------------------------------- approve and versions


class TestApprove:
    def test_researcher_cannot_approve(self, client, researcher_headers, sample_survey):
        assert client.post(f"/api/surveys/{sample_survey['id']}/approve", headers=researcher_headers).status_code == 403

    def test_admin_approves_as_version_1(self, approved_survey):
        assert approved_survey["current_version_no"] == 1
        assert approved_survey["draft"] is None
        assert approved_survey["versions"][0]["version_no"] == 1
        assert approved_survey["versions"][0]["question_count"] == 18
        assert approved_survey["versions"][0]["approved_by"] == "Admin"

    def test_broken_draft_cannot_be_approved(self, client, admin_headers, researcher_headers, broken_text):
        survey = upload(client, researcher_headers, broken_text).json()
        r = client.post(f"/api/surveys/{survey['id']}/approve", headers=admin_headers)
        assert r.status_code == 409
        assert "11 errors" in r.json()["detail"]
        assert len(r.json()["issues"]) == 11

    def test_nothing_to_approve(self, client, admin_headers, approved_survey):
        assert client.post(f"/api/surveys/{approved_survey['id']}/approve", headers=admin_headers).status_code == 409

    def test_changed_file_becomes_version_2_and_version_1_stays_frozen(
        self, client, admin_headers, researcher_headers, approved_survey, sample_text
    ):
        upload(client, researcher_headers, edited(sample_text))
        body = client.post(f"/api/surveys/{approved_survey['id']}/approve", headers=admin_headers).json()
        assert body["current_version_no"] == 2
        assert [v["version_no"] for v in body["versions"]] == [2, 1]
        assert body["title"] == "Smartphone Usage Study 2026"
        v1 = client.get(f"/api/surveys/{approved_survey['id']}/versions/1", headers=researcher_headers).json()
        assert "Smartphone Usage Study 2026" not in v1["text"]

    def test_unchanged_file_is_not_a_new_version(self, client, admin_headers, researcher_headers, approved_survey, sample_text):
        upload(client, researcher_headers, sample_text)
        r = client.post(f"/api/surveys/{approved_survey['id']}/approve", headers=admin_headers)
        assert r.status_code == 409
        assert "same as version 1" in r.json()["detail"]

    def test_version_view_has_clean_questions(self, client, researcher_headers, approved_survey):
        v1 = client.get(f"/api/surveys/{approved_survey['id']}/versions/1", headers=researcher_headers).json()
        q7 = next(q for q in v1["questions"] if q["qid"] == "q7")
        assert q7["rules"] == {"options_from": "q6"}
        assert v1["quotas"][2] == {"question_qid": "q4", "value": "Mumbai", "target": 80}
        assert client.get(f"/api/surveys/{approved_survey['id']}/versions/9", headers=researcher_headers).status_code == 404


# --------------------------------------------------------------------------- live, deadline, close


class TestLiveAndClose:
    def test_cannot_go_live_before_approval(self, client, admin_headers, sample_survey):
        r = client.post(f"/api/surveys/{sample_survey['id']}/go-live", headers=admin_headers)
        assert r.status_code == 409

    def test_researcher_cannot_go_live_or_close(self, client, researcher_headers, approved_survey):
        sid = approved_survey["id"]
        assert client.post(f"/api/surveys/{sid}/go-live", headers=researcher_headers).status_code == 403
        assert client.post(f"/api/surveys/{sid}/close", headers=researcher_headers).status_code == 403

    def test_go_live_with_default_deadline_of_15_days(self, client, admin_headers, approved_survey):
        body = client.post(f"/api/surveys/{approved_survey['id']}/go-live", headers=admin_headers).json()
        assert body["status"] == "live"
        deadline = datetime.fromisoformat(body["deadline"])
        expected = datetime.now(timezone.utc) + timedelta(days=15)
        assert abs((deadline - expected).total_seconds()) < 60

    def test_go_live_with_own_deadline(self, client, admin_headers, approved_survey):
        when = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
        body = client.post(f"/api/surveys/{approved_survey['id']}/go-live", json={"deadline": when}, headers=admin_headers).json()
        assert body["deadline"].startswith(when[:16])

    def test_deadline_in_the_past_is_refused(self, client, admin_headers, approved_survey):
        when = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        r = client.post(f"/api/surveys/{approved_survey['id']}/go-live", json={"deadline": when}, headers=admin_headers)
        assert r.status_code == 422

    def test_extend_deadline(self, client, admin_headers, approved_survey):
        sid = approved_survey["id"]
        client.post(f"/api/surveys/{sid}/go-live", headers=admin_headers)
        when = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        body = client.patch(f"/api/surveys/{sid}/deadline", json={"deadline": when}, headers=admin_headers).json()
        assert body["deadline"].startswith(when[:16])

    def test_close_by_team(self, client, admin_headers, approved_survey):
        sid = approved_survey["id"]
        client.post(f"/api/surveys/{sid}/go-live", headers=admin_headers)
        body = client.post(f"/api/surveys/{sid}/close", headers=admin_headers).json()
        assert body["status"] == "closed" and body["closed_reason"] == "closed_by_team"
        assert client.post(f"/api/surveys/{sid}/close", headers=admin_headers).status_code == 409

    def test_closes_itself_when_the_deadline_passes(self, client, db, admin_headers, approved_survey):
        sid = approved_survey["id"]
        client.post(f"/api/surveys/{sid}/go-live", headers=admin_headers)
        survey = db.get(Survey, sid)
        db.refresh(survey)
        survey.deadline = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()
        listed = client.get("/api/surveys", headers=admin_headers).json()[0]
        assert listed["status"] == "closed" and listed["closed_reason"] == "deadline_passed"

    def test_reopen_a_closed_survey(self, client, admin_headers, approved_survey):
        sid = approved_survey["id"]
        client.post(f"/api/surveys/{sid}/go-live", headers=admin_headers)
        client.post(f"/api/surveys/{sid}/close", headers=admin_headers)
        body = client.post(f"/api/surveys/{sid}/go-live", headers=admin_headers).json()
        assert body["status"] == "live" and body["closed_reason"] is None

    def test_new_version_while_live_keeps_it_live(self, client, admin_headers, researcher_headers, approved_survey, sample_text):
        sid = approved_survey["id"]
        client.post(f"/api/surveys/{sid}/go-live", headers=admin_headers)
        upload(client, researcher_headers, edited(sample_text))
        body = client.post(f"/api/surveys/{sid}/approve", headers=admin_headers).json()
        assert body["status"] == "live" and body["current_version_no"] == 2


def test_many_surveys_listed_newest_first(client, researcher_headers, sample_text, broken_text):
    upload(client, researcher_headers, sample_text)
    upload(client, researcher_headers, broken_text)
    slugs = [s["slug"] for s in client.get("/api/surveys", headers=researcher_headers).json()]
    assert slugs == ["snack_study", "smartphone_study"]
