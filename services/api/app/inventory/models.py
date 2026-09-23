"""
ORM models for the Nexova inventory domain -- Asset, AssetEntry, AssetExit.

current_stock is deliberately NOT a column anywhere in this file. Per
CONTEXT.md: "Stock levels cannot be modified directly." It's computed
in the service layer from AssetEntry/AssetExit history and only ever
appears in a response schema (schemas.py), never as a persisted field.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


class Asset(SQLModel, table=True):
    __tablename__ = "assets"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    sku: str = Field(unique=True, index=True)
    category: str
    office: str


class AssetEntry(SQLModel, table=True):
    """A purchase or supplier delivery received by Nexova -- increases
    an asset's stock."""

    __tablename__ = "asset_entries"

    id: Optional[int] = Field(default=None, primary_key=True)
    asset_id: int = Field(foreign_key="assets.id", index=True)
    quantity: int
    supplier: str
    office: str
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    # String, not a FK -- user_uuid references a TinyDB user, and
    # per CONTEXT.md there is no User table replicated in Supabase.
    user_uuid: str


class AssetExit(SQLModel, table=True):
    """An asset allocation to an employee, or a consumption event --
    decreases an asset's stock."""

    __tablename__ = "asset_exits"

    id: Optional[int] = Field(default=None, primary_key=True)
    asset_id: int = Field(foreign_key="assets.id", index=True)
    quantity: int
    exit_type: str  # "allocation" | "consumption" -- validated in schemas.py
    assigned_to: Optional[str] = None
    office: str
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    user_uuid: str
