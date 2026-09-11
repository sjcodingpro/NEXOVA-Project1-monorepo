"""
Auth security primitives: password hashing, JWT tokens, and the
get_current_user dependency used to protect routes.
"""

import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.hash import bcrypt

from app.database import get_users_table

# --- Configuration -----------------------------------------------------
# Never hardcode the secret. In dev, fall back to a clearly-marked
# placeholder so the app still boots, but this must be set for real use.
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-insecure-placeholder-change-me")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
RESET_TOKEN_EXPIRE_MINUTES = int(os.environ.get("RESET_TOKEN_EXPIRE_MINUTES", "30"))

# Used purely to register the Bearer auth scheme in OpenAPI (so Swagger
# shows the Authorize button) and to extract the token from the
# Authorization header. Login itself is a plain JSON POST, not an
# OAuth2 form -- consistent with every other endpoint in this API.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


# --- Password hashing ----------------------------------------------------

def hash_password(plain_password: str) -> str:
    return bcrypt.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.verify(plain_password, hashed_password)


# --- JWT tokens ------------------------------------------------------------

def create_access_token(user_id: int, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Raises JWTError on any invalid/expired/malformed token."""
    return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])


def create_reset_token(user_id: int) -> str:
    """A short-lived, single-purpose token for the password reset flow.
    Distinct 'type' claim from access tokens so one can never be used
    in place of the other. Carries a random 'jti' so this specific
    token (not just "any token issued around this time") can be
    marked used after a single successful reset."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": "reset",
        "jti": secrets.token_urlsafe(16),
        "iat": now,
        "exp": now + timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def validate_reset_token(token: str, user: dict) -> Optional[str]:
    """Returns the token's jti if it's a valid, not-yet-used reset
    token for this user; otherwise None.

    A JWT exp claim alone can't be invalidated after a single use, so
    this also checks the token's unique jti against the user's
    last_used_reset_jti -- once a specific token has been used to
    reset the password, that exact jti is recorded, and any later
    attempt to reuse the same token is rejected. (Comparing timestamps
    instead of an explicit per-token id was tried first, but a JWT's
    iat is truncated to whole seconds while stored timestamps carry
    microseconds, which caused incorrect rejections/acceptances for
    tokens issued or reused within the same second -- an explicit jti
    has no such ambiguity.)
    """
    try:
        payload = decode_token(token)
    except JWTError:
        return None

    if payload.get("type") != "reset":
        return None

    user_id_raw = payload.get("sub")
    if user_id_raw is None:
        return None

    try:
        user_id = int(user_id_raw)
    except (TypeError, ValueError):
        return None

    if user_id != user.get("id"):
        return None

    jti = payload.get("jti")
    if not jti:
        return None

    if jti == user.get("last_used_reset_jti"):
        return None

    return jti


# --- get_current_user dependency --------------------------------------------

def get_current_user(token: Optional[str] = Depends(oauth2_scheme)) -> dict:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not token:
        raise unauthorized

    try:
        payload = decode_token(token)
    except JWTError:
        raise unauthorized

    if payload.get("type") != "access":
        raise unauthorized

    user_id_raw = payload.get("sub")
    if user_id_raw is None:
        raise unauthorized

    try:
        user_id = int(user_id_raw)
    except (TypeError, ValueError):
        raise unauthorized

    table = get_users_table()
    user = table.get(doc_id=user_id)
    if user is None:
        raise unauthorized

    user = dict(user)
    user["id"] = user_id
    return user
