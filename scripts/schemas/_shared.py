"""Shared sub-models reused across multiple document payload schemas."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class FormulaComponent(BaseModel):
    ingredient: str = Field(description="Ingredient name")
    amount: Optional[float] = Field(default=None, description="Amount per serving as a number")
    unit: Optional[str] = Field(default=None, description="Unit of measurement (e.g. 'mg', 'g', 'mcg', 'IU')")


class SupplementsFact(BaseModel):
    ingredient: Optional[str] = Field(default=None, description="Ingredient name")
    amount_per_serving: Optional[str] = Field(default=None, description="Amount per serving with unit")
    daily_value_percent: Optional[str] = Field(default=None, description="Percent daily value (%DV)")


class CompanyInfo(BaseModel):
    name: Optional[str] = Field(default=None, description="Company name")
    address: Optional[str] = Field(default=None, description="Full address")
    email: Optional[str] = Field(default=None, description="Contact email")
    phone: Optional[str] = Field(default=None, description="Contact phone")
