"""
Tests for POST /auth/reset-password.

Business logic under test: does a valid reset token actually change the
password, and -- this is the security-critical part -- is a token
rejected the second time it's used? This directly targets the class of
bug described in the README (token logic silently breaking): a reset
token that could be replayed would let anyone who intercepted one link
reset the password repeatedly.
"""

from app.auth.security import create_reset_token, verify_password
from app.users import service as users_service


class TestResetPasswordHappyPath:
    def test_valid_token_changes_the_password(self, client, make_user):
        user_id, email, old_password = make_user()
        token = create_reset_token(user_id)

        response = client.post(
            "/auth/reset-password", json={"token": token, "new_password": "brandnewpassword123"}
        )

        assert response.status_code == 200
        updated = users_service.get_user_by_id(user_id)
        assert verify_password("brandnewpassword123", updated["hashed_password"])
        assert not verify_password(old_password, updated["hashed_password"])


class TestResetPasswordEdgeCases:
    def test_the_same_reset_token_cannot_be_used_twice(self, client, make_user):
        """Edge case, and the single most important test in this
        endpoint: reusing a token after a successful reset must fail.
        This is exactly the kind of token-lifecycle bug the README's
        incident describes -- a subtle break here has real security
        impact, not just a UX annoyance."""
        user_id, _, _ = make_user()
        token = create_reset_token(user_id)

        first_attempt = client.post(
            "/auth/reset-password", json={"token": token, "new_password": "firstnewpassword"}
        )
        second_attempt = client.post(
            "/auth/reset-password", json={"token": token, "new_password": "secondnewpassword"}
        )

        assert first_attempt.status_code == 200
        assert second_attempt.status_code == 400

    def test_new_password_shorter_than_the_minimum_is_rejected(self, client, make_user):
        user_id, _, _ = make_user()
        token = create_reset_token(user_id)

        response = client.post("/auth/reset-password", json={"token": token, "new_password": "short"})

        assert response.status_code == 422


class TestResetPasswordFailureModes:
    def test_malformed_token_is_rejected(self, client):
        response = client.post(
            "/auth/reset-password", json={"token": "not-a-jwt-at-all", "new_password": "somepassword123"}
        )

        assert response.status_code == 400

    def test_access_token_cannot_be_used_as_a_reset_token(self, client, make_user):
        """Failure mode mirroring test_me.py's equivalent check in the
        other direction: an access token must not work here either,
        since reset-password relies on the 'type' claim being 'reset'."""
        from app.auth.security import create_access_token

        user_id, _, _ = make_user()
        access_token = create_access_token(user_id, "user")

        response = client.post(
            "/auth/reset-password", json={"token": access_token, "new_password": "somepassword123"}
        )

        assert response.status_code == 400

    def test_token_for_a_deleted_user_is_rejected(self, client, make_user):
        user_id, _, _ = make_user()
        token = create_reset_token(user_id)
        users_service.delete_user(user_id)

        response = client.post(
            "/auth/reset-password", json={"token": token, "new_password": "somepassword123"}
        )

        assert response.status_code == 400

    def test_token_with_a_non_numeric_sub_claim_is_rejected(self, client):
        """Failure mode: a hand-crafted or corrupted token whose 'sub'
        claim isn't a valid integer must be rejected cleanly, not raise
        an unhandled ValueError from int(). This is a distinct code
        path from 'malformed JWT' -- the JWT itself is well-formed and
        correctly signed, only its payload content is wrong."""
        from datetime import datetime, timedelta, timezone
        from jose import jwt
        from app.auth.security import JWT_ALGORITHM, JWT_SECRET_KEY

        bad_payload = {
            "sub": "not-a-number",
            "type": "reset",
            "jti": "whatever",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
        }
        bad_token = jwt.encode(bad_payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

        response = client.post(
            "/auth/reset-password", json={"token": bad_token, "new_password": "somepassword123"}
        )

        assert response.status_code == 400
