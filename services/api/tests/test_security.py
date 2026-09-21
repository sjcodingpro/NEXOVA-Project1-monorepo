"""
Direct unit tests on app.auth.security's primitives -- token creation,
decoding, and expiry; password hashing. These don't go through any
endpoint; they test the functions the README's incident story is
actually about ("a small refactor broke token expiration logic, no
tests caught it").
"""

from datetime import datetime, timedelta, timezone

import pytest
from jose import JWTError, jwt

from app.auth.security import (
    JWT_ALGORITHM,
    JWT_SECRET_KEY,
    create_access_token,
    create_reset_token,
    decode_token,
    hash_password,
    verify_password,
)


class TestTokenCreationHappyPath:
    def test_access_token_round_trips_correctly(self):
        token = create_access_token(user_id=42, role="admin")

        payload = decode_token(token)

        assert payload["sub"] == "42"
        assert payload["role"] == "admin"
        assert payload["type"] == "access"

    def test_reset_token_carries_a_unique_jti_each_time(self):
        """Edge case: two reset tokens issued for the same user must
        not share a jti, or the replay-prevention logic in
        validate_reset_token would be defeated."""
        token_a = create_reset_token(user_id=1)
        token_b = create_reset_token(user_id=1)

        jti_a = decode_token(token_a)["jti"]
        jti_b = decode_token(token_b)["jti"]

        assert jti_a != jti_b


class TestTokenExpiry:
    """This is the class of test the README's incident story is
    directly about: does an expired token actually get rejected? A
    refactor that silently flips a comparison or drops the exp claim
    would only be caught here, not by an endpoint test using a
    freshly-issued token."""

    def test_a_token_expired_one_second_ago_is_rejected(self):
        now = datetime.now(timezone.utc)
        expired_payload = {
            "sub": "1",
            "role": "user",
            "type": "access",
            "iat": now - timedelta(minutes=31),
            "exp": now - timedelta(seconds=1),
        }
        expired_token = jwt.encode(expired_payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

        with pytest.raises(JWTError):
            decode_token(expired_token)

    def test_a_token_with_a_year_2000_expiry_is_rejected(self):
        """Edge case: a token whose exp is far in the past (not just
        barely expired) must be rejected the same way -- pins that
        expiry checking isn't accidentally only checking a narrow
        recent window."""
        ancient_payload = {
            "sub": "1",
            "role": "user",
            "type": "access",
            "iat": datetime(2000, 1, 1, tzinfo=timezone.utc),
            "exp": datetime(2000, 1, 1, tzinfo=timezone.utc),
        }
        ancient_token = jwt.encode(ancient_payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

        with pytest.raises(JWTError):
            decode_token(ancient_token)

    def test_a_token_valid_for_one_more_second_is_still_accepted(self):
        """The boundary case in the other direction: a token that
        hasn't expired yet, even by a hair, must still decode
        successfully -- guards against an off-by-one that rejects
        valid tokens too early."""
        now = datetime.now(timezone.utc)
        almost_expired_payload = {
            "sub": "1",
            "role": "user",
            "type": "access",
            "iat": now - timedelta(minutes=30),
            "exp": now + timedelta(seconds=1),
        }
        token = jwt.encode(almost_expired_payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

        payload = decode_token(token)  # must not raise

        assert payload["sub"] == "1"


class TestTokenFailureModes:
    def test_a_token_signed_with_a_different_secret_is_rejected(self):
        """Failure mode: a token forged with any other key -- including
        a plausible-looking one -- must never decode successfully."""
        forged = jwt.encode(
            {"sub": "1", "type": "access", "exp": datetime.now(timezone.utc) + timedelta(minutes=30)},
            "a-completely-different-secret",
            algorithm=JWT_ALGORITHM,
        )

        with pytest.raises(JWTError):
            decode_token(forged)

    def test_garbage_input_is_rejected(self):
        with pytest.raises(JWTError):
            decode_token("this-is-not-a-jwt")


class TestPasswordHashing:
    def test_correct_password_verifies_against_its_own_hash(self):
        hashed = hash_password("correcthorse123")

        assert verify_password("correcthorse123", hashed) is True

    def test_wrong_password_does_not_verify(self):
        hashed = hash_password("correcthorse123")

        assert verify_password("wrong-password", hashed) is False

    def test_hashing_the_same_password_twice_produces_different_hashes(self):
        """Edge case: bcrypt salts each hash, so identical inputs must
        not produce identical output -- a regression here (e.g.
        switching to an unsalted hash function) would be a serious
        security downgrade that a naive equality test wouldn't catch."""
        hash_one = hash_password("correcthorse123")
        hash_two = hash_password("correcthorse123")

        assert hash_one != hash_two
        assert verify_password("correcthorse123", hash_one)
        assert verify_password("correcthorse123", hash_two)


class TestValidateResetTokenDirectly:
    """Unit tests directly against validate_reset_token, rather than
    through the /reset-password endpoint -- these pin the exact branch
    logic (type check, sub parsing, user-id match, jti presence) that
    the endpoint-level tests in test_reset_password.py can't isolate
    from each other."""

    def test_access_type_token_is_rejected_at_the_type_check(self):
        access_token = create_access_token(user_id=1, role="user")

        from app.auth.security import validate_reset_token
        result = validate_reset_token(access_token, {"id": 1})

        assert result is None

    def test_token_for_a_different_user_id_is_rejected(self):
        token_for_user_1 = create_reset_token(user_id=1)

        from app.auth.security import validate_reset_token
        result = validate_reset_token(token_for_user_1, {"id": 2})

        assert result is None

    def test_returns_the_jti_on_a_genuinely_valid_unused_token(self):
        token = create_reset_token(user_id=7)

        from app.auth.security import validate_reset_token
        result = validate_reset_token(token, {"id": 7})

        assert result is not None
        assert result == decode_token(token)["jti"]

