"""
Pydantic models for the users domain. Credentials only -- display
name and contact data live on Profile, never here.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class Role(str, Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    USER = "user"


class UserCreate(BaseModel):
    """POST /users payload. Optional profile fields create the linked
    Profile in the same operation; they are never stored on User."""

    email: EmailStr
    password: str = Field(..., min_length=8)
    name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None


class UserUpdate(BaseModel):
    """PUT /users/{id} payload -- credential fields only."""

    email: Optional[EmailStr] = None
    role: Optional[Role] = None
    is_active: Optional[bool] = None


class UserOut(BaseModel):
    """Public-facing user record. Never includes hashed_password."""

    id: int
    email: EmailStr
    is_active: bool
    role: Role
    created_at: datetime
