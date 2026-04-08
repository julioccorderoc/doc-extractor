"""Payment proof schema."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class PaymentProofPayload(BaseModel):
    date: Optional[str] = Field(default=None, description="Payment date in YYYY-MM-DD format")
    payer: Optional[str] = Field(default=None, description="Name or account of the entity making the payment")
    payee: Optional[str] = Field(default=None, description="Name or account of the entity receiving the payment")
    amount: Optional[float] = Field(default=None, description="Payment amount as a number")
    currency: Optional[str] = Field(default=None, description="ISO 4217 currency code (e.g. 'USD', 'MXN')")
    confirmation_number: Optional[str] = Field(default=None, description="Payment confirmation or reference number")
    payment_method: Optional[str] = Field(
        default=None,
        description="Payment method or bank name (e.g. 'Zelle', 'ACH', 'Wire Transfer')",
    )
