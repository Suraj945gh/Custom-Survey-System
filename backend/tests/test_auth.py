"""Passwords, tokens, log in, roles, managing staff."""

from app.security import hash_password, make_token, read_token, verify_password


class TestPasswordsAndTokens:
    def test_password_is_hashed_and_checked(self):
        stored = hash_password("secret-pass")
        assert "secret-pass" not in stored
        assert verify_password("secret-pass", stored)
        assert not verify_password("wrong", stored)
        assert not verify_password("secret-pass", "garbage")

    def test_same_password_hashes_differently(self):
        assert hash_password("a") != hash_password("a")  # random salt

    def test_token_round_trip(self):
        assert read_token(make_token(7)) == 7

    def test_edited_or_broken_token_is_rejected(self):
        token = make_token(7)
        assert read_token("8" + token[1:]) is None  # changed user id
        assert read_token("nonsense") is None
        assert read_token("") is None

    def test_expired_token_is_rejected(self):
        assert read_token(make_token(7, hours=-1)) is None


class TestLogin:
    def test_login_returns_token_and_user(self, client, admin):
        r = client.post("/api/auth/login", json={"email": "ADMIN@test.local ", "password": "password123"})
        assert r.status_code == 200
        body = r.json()
        assert body["user"]["role"] == "admin"
        me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['token']}"})
        assert me.json()["email"] == "admin@test.local"

    def test_wrong_password(self, client, admin):
        r = client.post("/api/auth/login", json={"email": "admin@test.local", "password": "nope"})
        assert r.status_code == 401
        assert r.json()["detail"] == "Wrong email or password."

    def test_unknown_email_gets_the_same_message(self, client):
        r = client.post("/api/auth/login", json={"email": "who@test.local", "password": "nope"})
        assert r.status_code == 401
        assert r.json()["detail"] == "Wrong email or password."

    def test_switched_off_account(self, client, db, admin):
        admin.is_active = False
        db.commit()
        assert client.post("/api/auth/login", json={"email": "admin@test.local", "password": "password123"}).status_code == 403

    def test_routes_need_a_token(self, client):
        assert client.get("/api/surveys").status_code == 401
        assert client.get("/api/surveys", headers={"Authorization": "Bearer fake"}).status_code == 401


class TestUsers:
    NEW = {"email": "new@test.local", "name": "New Person", "role": "researcher", "password": "longenough"}

    def test_admin_creates_a_researcher_who_can_log_in(self, client, admin_headers):
        r = client.post("/api/users", json=self.NEW, headers=admin_headers)
        assert r.status_code == 201
        assert client.post("/api/auth/login", json={"email": "new@test.local", "password": "longenough"}).status_code == 200

    def test_researcher_cannot_manage_users(self, client, researcher_headers):
        assert client.get("/api/users", headers=researcher_headers).status_code == 403
        assert client.post("/api/users", json=self.NEW, headers=researcher_headers).status_code == 403

    def test_duplicate_email(self, client, admin_headers):
        client.post("/api/users", json=self.NEW, headers=admin_headers)
        assert client.post("/api/users", json=self.NEW, headers=admin_headers).status_code == 409

    def test_bad_input_is_rejected(self, client, admin_headers):
        assert client.post("/api/users", json={**self.NEW, "role": "boss"}, headers=admin_headers).status_code == 422
        assert client.post("/api/users", json={**self.NEW, "password": "short"}, headers=admin_headers).status_code == 422
        assert client.post("/api/users", json={**self.NEW, "email": "not-an-email"}, headers=admin_headers).status_code == 422
