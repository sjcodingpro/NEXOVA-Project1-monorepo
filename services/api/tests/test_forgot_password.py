"""
Tests for POST /auth/forgot-password.

Business logic under test: does the endpoint avoid leaking whether an
email is registered, and does it stay resilient if the email provider
fails? The actual email send is mocked -- this suite tests decision
logic, not whether Resend's API works.
"""

import pytest


class TestForgotPasswordHappyPath:
    def test_registered_email_triggers_a_send_and_returns_generic_message(
        self, client, make_user, monkeypatch
    ):
        _, email, _ = make_user()
        sent = {}

        def fake_send(to_email, token):
            sent["to_email"] = to_email
            sent["token"] = token

        monkeypatch.setattr("app.auth.router.send_reset_email", fake_send)

        response = client.post("/auth/forgot-password", json={"email": email})

        assert response.status_code == 200
        assert sent["to_email"] == email
        assert sent["token"]  # a real token was generated and passed through


class TestForgotPasswordEdgeCases:
    def test_unregistered_email_gets_the_identical_response_and_no_send(
        self, client, monkeypatch
    ):
        """Edge case (and the core security property of this endpoint):
        an unregistered email must be indistinguishable from a
        registered one at the response level, and must never trigger a
        send attempt at all."""
        send_was_called = False

        def fake_send(to_email, token):
            nonlocal send_was_called
            send_was_called = True

        monkeypatch.setattr("app.auth.router.send_reset_email", fake_send)

        registered_response = client.post("/auth/forgot-password", json={"email": "ghost@nowhere.com"})

        assert registered_response.status_code == 200
        assert registered_response.json()["message"] == "If that address is registered, a reset link has been sent."
        assert send_was_called is False

    def test_response_message_is_identical_whether_or_not_the_email_exists(
        self, client, make_user, monkeypatch
    ):
        monkeypatch.setattr("app.auth.router.send_reset_email", lambda to_email, token: None)
        _, email, _ = make_user()

        exists = client.post("/auth/forgot-password", json={"email": email})
        does_not_exist = client.post("/auth/forgot-password", json={"email": "nobody@example.com"})

        assert exists.json() == does_not_exist.json()


class TestForgotPasswordFailureModes:
    def test_email_provider_failure_still_returns_200_with_the_generic_message(
        self, client, make_user, monkeypatch
    ):
        """Failure mode: send_reset_email raising (provider outage, bad
        API key, etc.) must never change the response -- the endpoint's
        whole security model depends on always returning 200 with the
        same message regardless of what happens internally."""
        _, email, _ = make_user()

        def failing_send(to_email, token):
            raise RuntimeError("Resend API is down")

        monkeypatch.setattr("app.auth.router.send_reset_email", failing_send)

        response = client.post("/auth/forgot-password", json={"email": email})

        assert response.status_code == 200
        assert response.json()["message"] == "If that address is registered, a reset link has been sent."

    def test_malformed_email_is_rejected_before_any_send_is_attempted(self, client, monkeypatch):
        send_was_called = False

        def fake_send(to_email, token):
            nonlocal send_was_called
            send_was_called = True

        monkeypatch.setattr("app.auth.router.send_reset_email", fake_send)

        response = client.post("/auth/forgot-password", json={"email": "not-an-email"})

        assert response.status_code == 422
        assert send_was_called is False
