"""
/auth endpoints: login (public) and me (protected).
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.models import LoginRequest, MeResponse, TokenResponse
from app.auth.security import create_access_token, get_current_user, verify_password
from app.profiles import service as profiles_service
from app.users import service as users_service

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
