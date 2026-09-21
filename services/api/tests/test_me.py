"""
Tests for GET /auth/me.

Business logic under test: does the endpoint correctly resolve "who is
calling" from the token, and handle the case where that user has no
profile yet?
"""


class TestMeHappyPath:
    def test_valid_token_returns_the_correct_user_identity(self, client, make_user, auth_headers):
        user_id, email, _ = make_user()

        response = client.get("/auth/me", headers=auth_headers(user_id))

        assert response.status_code == 200
        body = response.json()
        assert body["id"] == user_id
        assert body["email"] == email


class TestMeEdgeCases:
    def test_user_with_no_profile_yet_still_returns_successfully(self, client, make_user, auth_headers):
        """Edge case: a user record can exist with no linked profile
        (e.g. created directly, bypassing the normal registration flow
        that also creates a profile). The endpoint must not 500 or
        require a profile to exist -- MeResponse.profile is Optional."""
        user_id, _, _ = make_user()

        response = client.get("/auth/me", headers=auth_headers(user_id))

        assert response.status_code == 200
        assert response.json()["profile"] is None

    def test_role_from_the_token_is_ignored_in_favor_of_the_stored_role(self, client, make_user, auth_headers):
        """Edge case: the token carries a 'role' claim, but /me should
        report the user's *current* stored role, not whatever role was
        baked into the token at login time -- otherwise a role change
        (e.g. admin demoting a user) wouldn't take effect until the
        token itself expired."""
        user_id, _, _ = make_user(role="user")
        # Simulate a token that was issued while the user was still an
        # admin (e.g. right before a demotion).
        from app.auth.security import create_access_token
        stale_token = create_access_token(user_id, "admin")

        response = client.get("/auth/me", headers={"Authorization": f"Bearer {stale_token}"})

        assert response.status_code == 200
        assert response.json()["role"] == "user"


class TestMeFailureModes:
    def test_missing_token_is_rejected(self, client):
        response = client.get("/auth/me")

        assert response.status_code == 401

    def test_malformed_token_is_rejected(self, client):
        response = client.get("/auth/me", headers={"Authorization": "Bearer not-a-real-jwt"})

        assert response.status_code == 401

    def test_reset_token_cannot_be_used_as_an_access_token(self, client, make_user):
        """Failure mode specific to this app's token design: a reset
        token and an access token are both valid JWTs signed with the
        same secret, differentiated only by the 'type' claim. If that
        check were ever removed, a password-reset link would double as
        a login token -- this test pins that it can't."""
        from app.auth.security import create_reset_token

        user_id, _, _ = make_user()
        reset_token = create_reset_token(user_id)

        response = client.get("/auth/me", headers={"Authorization": f"Bearer {reset_token}"})

        assert response.status_code == 401
