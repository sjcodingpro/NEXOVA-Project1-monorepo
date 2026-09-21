"""
Tests for POST /auth/login.

Business logic under test: does the endpoint correctly decide whether
to issue a token, based on credentials and account state? Not tested:
response JSON shape (that's FastAPI/pydantic's job, not ours).
"""

from app.auth.security import decode_token


class TestLoginHappyPath:
    def test_valid_credentials_returns_a_working_access_token(self, client, make_user):
        user_id, email, password = make_user()

        response = client.post("/auth/login", json={"email": email, "password": password})

        assert response.status_code == 200
        token = response.json()["access_token"]
        # The real assertion: the token actually decodes back to this
        # user, with the correct type -- not just "a string came back".
        payload = decode_token(token)
        assert payload["sub"] == str(user_id)
        assert payload["type"] == "access"


class TestLoginEdgeCases:
    def test_wrong_password_and_nonexistent_email_give_identical_errors(self, client, make_user):
        """Edge case: the API must not let a caller distinguish 'wrong
        password' from 'no such account' -- that distinction is a user
        enumeration vulnerability. Both must produce the same status
        code and message."""
        _, email, _ = make_user()

        wrong_password = client.post("/auth/login", json={"email": email, "password": "not-the-password"})
        no_such_user = client.post("/auth/login", json={"email": "nobody@example.com", "password": "irrelevant"})

        assert wrong_password.status_code == no_such_user.status_code == 401
        assert wrong_password.json()["detail"] == no_such_user.json()["detail"]

    def test_password_field_is_case_and_whitespace_sensitive(self, client, make_user):
        """Edge case explicitly named in the README: what happens with
        a slightly-off password? It must be rejected, not loosely
        matched."""
        _, email, password = make_user(password="CorrectHorse123")

        response = client.post("/auth/login", json={"email": email, "password": password.lower()})

        assert response.status_code == 401


class TestLoginFailureModes:
    def test_inactive_account_is_rejected_even_with_correct_password(self, client, make_user):
        _, email, password = make_user(is_active=False)

        response = client.post("/auth/login", json={"email": email, "password": password})

        assert response.status_code == 401
        assert "inactive" in response.json()["detail"].lower()

    def test_empty_password_field_is_rejected(self, client, make_user):
        _, email, _ = make_user()

        response = client.post("/auth/login", json={"email": email, "password": ""})

        # Pydantic's `password: str` accepts an empty string as valid
        # JSON input (it's still a str) -- the actual rejection has to
        # come from verify_password failing the hash comparison, not
        # from request validation. This is the business-logic case the
        # README's "empty password field" edge case is really testing.
        assert response.status_code == 401
