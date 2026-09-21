"""
Tests for POST /auth/change-password.

Business logic under test: does the endpoint require proof of the
current password before allowing a change, for an already-authenticated
user?
"""

from app.auth.security import verify_password
from app.users import service as users_service


class TestChangePasswordHappyPath:
    def test_correct_current_password_allows_the_change(self, client, make_user, auth_headers):
        user_id, _, old_password = make_user()

        response = client.post(
            "/auth/change-password",
            json={"current_password": old_password, "new_password": "newpassword123"},
            headers=auth_headers(user_id),
        )

        assert response.status_code == 200
        updated = users_service.get_user_by_id(user_id)
        assert verify_password("newpassword123", updated["hashed_password"])


class TestChangePasswordEdgeCases:
    def test_new_password_identical_to_the_current_one_is_still_accepted(
        self, client, make_user, auth_headers
    ):
        """Edge case: the API doesn't forbid 'changing' to the same
        password. This documents that as accepted behavior (there's no
        password-history check in this app) rather than leaving it
        untested and assumed."""
        user_id, _, password = make_user()

        response = client.post(
            "/auth/change-password",
            json={"current_password": password, "new_password": password},
            headers=auth_headers(user_id),
        )

        assert response.status_code == 200

    def test_new_password_below_minimum_length_is_rejected(self, client, make_user, auth_headers):
        user_id, _, password = make_user()

        response = client.post(
            "/auth/change-password",
            json={"current_password": password, "new_password": "short"},
            headers=auth_headers(user_id),
        )

        assert response.status_code == 422


class TestChangePasswordFailureModes:
    def test_wrong_current_password_is_rejected(self, client, make_user, auth_headers):
        user_id, _, _ = make_user()

        response = client.post(
            "/auth/change-password",
            json={"current_password": "definitely-wrong", "new_password": "newpassword123"},
            headers=auth_headers(user_id),
        )

        assert response.status_code == 400

    def test_no_token_is_rejected_before_any_password_check_happens(self, client, make_user):
        user_id, _, password = make_user()

        response = client.post(
            "/auth/change-password",
            json={"current_password": password, "new_password": "newpassword123"},
        )

        assert response.status_code == 401
        # The password must be unchanged -- the request never should
        # have reached the password-comparison logic at all.
        unchanged = users_service.get_user_by_id(user_id)
        assert verify_password(password, unchanged["hashed_password"])
