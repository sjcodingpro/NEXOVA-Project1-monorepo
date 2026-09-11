"""
/users endpoints: registration (public) plus protected CRUD.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.security import get_current_user
from app.users import service as users_service
from app.users.models import Role, UserCreate, UserOut, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


def _require_self_or_admin(current_user: dict, target_id: int):
    if current_user["id"] != target_id and current_user["role"] != Role.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to act on this user.",
        )


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register_user(payload: UserCreate):
    existing = users_service.get_user_by_email(payload.email)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email already exists.",
        )
    return users_service.create_user(payload)


@router.get("", response_model=list[UserOut])
async def list_users(current_user: dict = Depends(get_current_user)):
    return users_service.list_users()


@router.get("/{user_id}", response_model=UserOut)
async def get_user(user_id: int, current_user: dict = Depends(get_current_user)):
    user = users_service.get_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return user


@router.put("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: int,
    payload: UserUpdate,
    current_user: dict = Depends(get_current_user),
):
    existing = users_service.get_user_by_id(user_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    _require_self_or_admin(current_user, user_id)

    if payload.role is not None and current_user["role"] != Role.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only an admin can change a user's role.",
        )

    updated = users_service.update_user(
        user_id, email=payload.email, role=payload.role, is_active=payload.is_active
    )
    return updated


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: int, current_user: dict = Depends(get_current_user)):
    existing = users_service.get_user_by_id(user_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    _require_self_or_admin(current_user, user_id)

    users_service.delete_user(user_id)
    return None
