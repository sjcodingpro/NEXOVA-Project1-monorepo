"""
/profiles endpoints -- always scoped to the authenticated caller.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.security import get_current_user
from app.profiles import service as profiles_service
from app.profiles.models import ProfileOut, ProfileUpdate

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.get("/me", response_model=ProfileOut)
async def get_my_profile(current_user: dict = Depends(get_current_user)):
    profile = profiles_service.get_profile_by_user_id(current_user["id"])
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found.")
    return profile


@router.put("/me", response_model=ProfileOut)
async def update_my_profile(
    payload: ProfileUpdate,
    current_user: dict = Depends(get_current_user),
):
    profile = profiles_service.update_profile(
        current_user["id"],
        name=payload.name,
        phone=payload.phone,
        address=payload.address,
    )
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found.")
    return profile
