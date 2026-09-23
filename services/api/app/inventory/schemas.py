"""
Request/response schemas for the inventory domain. Deliberately separate
from app.inventory.models (the ORM layer) -- per the milestone brief,
"never return a raw ORM object from an endpoint," even where the field
sets overlap almost completely.
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, field_validator, model_validator

VALID_CATEGORIES = {"hardware", "peripherals", "office_supplies", "training_materials"}
VALID_OFFICES = {"Valencia", "Miami"}
VALID_EXIT_TYPES = {"allocation", "consumption"}


# --- Asset --------------------------------------------------------------

class AssetCreate(BaseModel):
    name: str
    sku: str
    category: str
    office: str

    @field_validator("category")
    @classmethod
    def category_must_be_known(cls, v: str) -> str:
        if v not in VALID_CATEGORIES:
            raise ValueError(f"category must be one of {sorted(VALID_CATEGORIES)}")
        return v

    @field_validator("office")
    @classmethod
    def office_must_be_known(cls, v: str) -> str:
        if v not in VALID_OFFICES:
            raise ValueError(f"office must be one of {sorted(VALID_OFFICES)}")
        return v


class AssetOut(BaseModel):
    id: int
    name: str
    sku: str
    category: str
    office: str
    # Computed in the service layer from AssetEntry/AssetExit history --
    # never a stored column. See models.py's module docstring.
    current_stock: int


# --- AssetEntry (inbound) ------------------------------------------------

class AssetEntryCreate(BaseModel):
    asset_id: int
    quantity: int
    supplier: str
    office: str

    @field_validator("quantity")
    @classmethod
    def quantity_must_be_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("quantity must be a positive integer")
        return v

    @field_validator("office")
    @classmethod
    def office_must_be_known(cls, v: str) -> str:
        if v not in VALID_OFFICES:
            raise ValueError(f"office must be one of {sorted(VALID_OFFICES)}")
        return v


class AssetEntryOut(BaseModel):
    id: int
    asset_id: int
    quantity: int
    supplier: str
    office: str
    created_at: datetime
    user_uuid: str


# --- AssetExit (outbound) -------------------------------------------------

class AssetExitCreate(BaseModel):
    asset_id: int
    quantity: int
    exit_type: str
    assigned_to: Optional[str] = None
    office: str

    @field_validator("quantity")
    @classmethod
    def quantity_must_be_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("quantity must be a positive integer")
        return v

    @field_validator("exit_type")
    @classmethod
    def exit_type_must_be_known(cls, v: str) -> str:
        if v not in VALID_EXIT_TYPES:
            raise ValueError(f"exit_type must be one of {sorted(VALID_EXIT_TYPES)}")
        return v

    @field_validator("office")
    @classmethod
    def office_must_be_known(cls, v: str) -> str:
        if v not in VALID_OFFICES:
            raise ValueError(f"office must be one of {sorted(VALID_OFFICES)}")
        return v

    @model_validator(mode="after")
    def assigned_to_matches_exit_type(self) -> "AssetExitCreate":
        # CONTEXT.md: assigned_to is required when exit_type="allocation"
        # and must be null when exit_type="consumption".
        if self.exit_type == "allocation" and not self.assigned_to:
            raise ValueError("assigned_to is required when exit_type is 'allocation'")
        if self.exit_type == "consumption" and self.assigned_to is not None:
            raise ValueError("assigned_to must be null when exit_type is 'consumption'")
        return self


class AssetExitOut(BaseModel):
    id: int
    asset_id: int
    quantity: int
    exit_type: str
    assigned_to: Optional[str]
    office: str
    created_at: datetime
    user_uuid: str


# --- Combined order listing (GET /inventory/orders) -----------------------

class OrderOut(BaseModel):
    """A single row in the combined entries+exits listing. order_type
    discriminates which one this row actually is; the type-specific
    fields (supplier / exit_type+assigned_to) are None on the other
    kind rather than the schema being split into two response models --
    simpler for a single chronological feed."""

    order_type: Literal["inbound", "outbound"]
    id: int
    asset_id: int
    asset_name: str
    asset_sku: str
    quantity: int
    office: str
    created_at: datetime
    user_uuid: str
    supplier: Optional[str] = None
    exit_type: Optional[str] = None
    assigned_to: Optional[str] = None
