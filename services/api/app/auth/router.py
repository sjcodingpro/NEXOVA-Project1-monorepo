"""
/auth endpoints: login, me, and the password reset/change flows.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError

from app.auth.email import send_reset_email
from app.auth.models import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    MeResponse,
    ResetPasswordRequest,
    TokenResponse,
)
from app.auth.security import (
    create_access_token,
    create_reset_token,
    decode_token,
    get_current_user,
    hash_password,
    validate_reset_token,
    verify_password,
)
from app.profiles import service as profiles_service
from app.users import service as users_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest):
    invalid_credentials = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect email or password.",
    )

    user = users_service.get_user_by_email(payload.email)
    if user is None:
        raise invalid_credentials

    if not verify_password(payload.password, user["hashed_password"]):
        raise invalid_credentials

    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This account is inactive.",
        )

    token = create_access_token(user_id=user["id"], role=user["role"])
    return TokenResponse(access_token=token)


@router.get("/me", response_model=MeResponse)
async def read_current_user(current_user: dict = Depends(get_current_user)):
    profile = profiles_service.get_profile_by_user_id(current_user["id"])
    return MeResponse(
        id=current_user["id"],
        email=current_user["email"],
        role=current_user["role"],
        profile=profile,
    )


@router.post("/forgot-password")
async def forgot_password(payload: ForgotPasswordRequest):
    # Always returns the same response regardless of whether the email
    # exists -- an attacker must not be able to use this endpoint to
    # discover which addresses are registered.
    user = users_service.get_user_by_email(payload.email)
    if user is not None:
        token = create_reset_token(user["id"])
        try:
            send_reset_email(user["email"], token)
        except Exception:
            # Never let a send failure change the response or leak
            # anything to the client -- still always 200.
            logger.exception("Failed to send password reset email")

    return {"message": "If that address is registered, a reset link has been sent."}


@router.post("/reset-password")
async def reset_password(payload: ResetPasswordRequest):
    invalid_token = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid or expired token.",
    )

    try:
        raw_payload = decode_token(payload.token)
    except JWTError:
        raise invalid_token

    try:
        user_id = int(raw_payload.get("sub"))
    except (TypeError, ValueError):
        raise invalid_token

    user = users_service.get_user_by_id(user_id)
    if user is None:
        raise invalid_token

    if validate_reset_token(payload.token, user) is None:
        raise invalid_token

    new_hashed = hash_password(payload.new_password)
    users_service.bump_password_changed_at(user_id, new_hashed)

    return {"message": "Password has been reset successfully."}


@router.post("/change-password")
async def change_password(
    payload: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user),
):
    if not verify_password(payload.current_password, current_user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )

    new_hashed = hash_password(payload.new_password)
    users_service.bump_password_changed_at(current_user["id"], new_hashed)

    return {"message": "Password changed successfully."}
