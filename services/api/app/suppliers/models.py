"""
Pydantic models for Nexova's supplier directory.

Field names, valid categories, and allowed statuses match
CONTEXT-nexova.md (Milestone 09 -- Lightweight Storage API) exactly.
"""

from datetime import date, datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


class Country(str, Enum):
    SPAIN = "Spain"
    USA = "USA"


class Currency(str, Enum):
    EUR = "EUR"
    USD = "USD"


class Category(str, Enum):
    JOB_BOARDS = "job_boards"
    ATS_SOFTWARE = "ats_software"
    ASSESSMENT_TOOLS = "assessment_tools"
    TRAINING_PLATFORMS = "training_platforms"
    PAYROLL_AND_HR_SOFTWARE = "payroll_and_hr_software"
    VIDEO_INTERVIEW = "video_interview"
    BACKGROUND_CHECK = "background_check"
    OFFICE_AND_FACILITIES = "office_and_facilities"
    IT_AND_SOFTWARE_LICENSES = "it_and_software_licenses"


class SupplierStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"


# Business constraint from CONTEXT: a supplier's currency must match
# its country. The API must reject inconsistent combinations.
COUNTRY_CURRENCY_MAP = {
    Country.SPAIN: Currency.EUR,
    Country.USA: Currency.USD,
}


class SupplierBase(BaseModel):
    name: str = Field(..., min_length=1)
    country: Country
    categories: List[Category] = Field(..., min_length=1)
    monthly_rate: float = Field(..., gt=0)
    currency: Currency
    status: SupplierStatus
    contract_renewal_date: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    notes: Optional[str] = None

    @field_validator("contract_renewal_date")
    @classmethod
    def validate_renewal_date_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        try:
            date.fromisoformat(v)
        except ValueError:
            raise ValueError("contract_renewal_date must be in YYYY-MM-DD format")
        return v

    @model_validator(mode="after")
    def check_currency_matches_country(self):
        expected = COUNTRY_CURRENCY_MAP[self.country]
        if self.currency != expected:
            raise ValueError(
                f"currency must be {expected.value} for country {self.country.value}"
            )
        return self


class SupplierCreate(SupplierBase):
    """Payload for POST /suppliers. updated_at is system-generated, never accepted here."""

    pass


class Supplier(SupplierBase):
    """Full supplier record as stored and returned, including system fields."""

    id: int
    updated_at: datetime


class SupplierRateUpdate(BaseModel):
    monthly_rate: float = Field(..., gt=0)


class SupplierStatusUpdate(BaseModel):
    status: SupplierStatus
