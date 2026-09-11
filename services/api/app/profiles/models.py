"""
Pydantic models for the profiles domain -- display name and contact
data, linked one-to-one to a User via user_id.
"""

from typing import Optional

from pydantic import BaseModel


class ProfileOut(BaseModel):
    id: int
    user_id: int
    name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None


class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
