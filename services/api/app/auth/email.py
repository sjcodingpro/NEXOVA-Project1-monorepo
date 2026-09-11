"""
Transactional email via Resend, used for the password reset flow.
"""

import os

import resend

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000").rstrip("/")

# Resend's sandbox default sender -- works without domain verification,
# but (per Resend's dev-mode restriction) can only deliver to the email
# address the Resend account itself is registered under.
FROM_ADDRESS = os.environ.get("RESEND_FROM_ADDRESS", "onboarding@resend.dev")


def build_reset_url(token: str) -> str:
    return f"{FRONTEND_URL}/reset-password?token={token}"


def send_reset_email(to_email: str, token: str) -> None:
    """Sends the password reset link. Exceptions are intentionally not
    caught here -- the caller (forgot-password endpoint) always
    returns 200 regardless of what happens in this function, so a
    failed send never leaks anything to the client either way."""
    if not RESEND_API_KEY:
        raise RuntimeError("RESEND_API_KEY is not set. Check your .env.")

    resend.api_key = RESEND_API_KEY
    reset_url = build_reset_url(token)

    resend.Emails.send({
        "from": FROM_ADDRESS,
        "to": [to_email],
        "subject": "Reset your Nexova password",
        "text": (
            "We received a request to reset your Nexova password.\n\n"
            f"Reset it here: {reset_url}\n\n"
            "This link expires in 30 minutes. If you didn't request "
            "this, you can safely ignore this email."
        ),
    })
