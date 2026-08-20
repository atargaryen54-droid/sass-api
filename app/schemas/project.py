from pydantic import BaseModel
from app.schemas.enums import PaymentProvider, BillingFrequency
from typing import Optional
from datetime import datetime


class ProjectCreate(BaseModel):
    name: str
    payment_provider: PaymentProvider
    billing_frequency: BillingFrequency


class ProjectResponse(BaseModel):
    external_id: str
    name: str
    payment_provider: PaymentProvider
    billing_frequency: BillingFrequency
    next_billing_date: datetime

    class Config:
        from_attributes = True


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    payment_provider: Optional[PaymentProvider] = None
    billing_frequency: Optional[BillingFrequency] = None
