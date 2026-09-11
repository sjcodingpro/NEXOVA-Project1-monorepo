from typing import Optional

from pydantic import BaseModel, EmailStr

from app.profiles.models import ProfileOut
from app.users.models import Role


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeResponse(BaseModel):
    id: int
    email: EmailStr
    role: Role
    profile: Optional[ProfileOut] = None
