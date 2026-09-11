"""
Service layer for users -- pure functions against TinyDB, no
FastAPI/HTTP concerns here.
"""

from datetime import datetime, timezone
from typing import Optional

from app.auth.security import hash_password
from app.database import get_users_table
from app.profiles import service as profiles_service
from app.users.models import Role, UserCreate


def _row_to_user(doc) -> dict:
    data = dict(doc)
    data["id"] = doc.doc_id
    return data


def create_user(payload: UserCreate) -> dict:
    table = get_users_table()
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "email": payload.email,
        "hashed_password": hash_password(payload.password),
        "is_active": True,
        # New registrations always default to "user" regardless of
        # what the client sends -- there is no role field on
        # UserCreate at all, so there is nothing to override here.
        "role": Role.USER.value,
        "created_at": now,
        "password_changed_at": now,
    }
    doc_id = table.insert(record)

    profiles_service.create_profile(
        user_id=doc_id,
        name=payload.name,
        phone=payload.phone,
        address=payload.address,
    )

    return _row_to_user(table.get(doc_id=doc_id))


def get_user_by_id(user_id: int) -> Optional[dict]:
    table = get_users_table()
    doc = table.get(doc_id=user_id)
    if doc is None:
        return None
    return _row_to_user(doc)


def get_user_by_email(email: str) -> Optional[dict]:
    table = get_users_table()
    for doc in table.all():
        if doc.get("email") == email:
            return _row_to_user(doc)
    return None


def list_users() -> list[dict]:
    table = get_users_table()
    return [_row_to_user(doc) for doc in table.all()]


def update_user(user_id: int, email: Optional[str] = None, role: Optional[Role] = None, is_active: Optional[bool] = None) -> Optional[dict]:
    table = get_users_table()
    existing = table.get(doc_id=user_id)
    if existing is None:
        return None

    updates = {}
    if email is not None:
        updates["email"] = email
    if role is not None:
        updates["role"] = role.value
    if is_active is not None:
        updates["is_active"] = is_active

    if updates:
        table.update(updates, doc_ids=[user_id])

    return _row_to_user(table.get(doc_id=user_id))


def delete_user(user_id: int) -> bool:
    table = get_users_table()
    existing = table.get(doc_id=user_id)
    if existing is None:
        return False
    table.remove(doc_ids=[user_id])
    profiles_service.delete_profile_by_user_id(user_id)
    return True


def bump_password_changed_at(
    user_id: int, new_hashed_password: str, used_reset_jti: Optional[str] = None
) -> None:
    """Used by both change-password and reset-password to actually
    apply a new password. When called from reset-password, also
    records that specific token's jti as used, so it can never be
    replayed -- see validate_reset_token for why an explicit jti is
    used instead of comparing timestamps."""
    table = get_users_table()
    updates = {
        "hashed_password": new_hashed_password,
        "password_changed_at": datetime.now(timezone.utc).isoformat(),
    }
    if used_reset_jti is not None:
        updates["last_used_reset_jti"] = used_reset_jti

    table.update(updates, doc_ids=[user_id])
