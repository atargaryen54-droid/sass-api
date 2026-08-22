from pydantic import BaseModel, ConfigDict
from app.schemas.enums import PaymentProvider, BillingFrequency
from typing import Optional
from datetime import datetime


class ProjectCreate(BaseModel):
    name: str
    payment_provider: PaymentProvider
    billing_frequency: BillingFrequency


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    external_id: str
    name: str
    payment_provider: PaymentProvider
    billing_frequency: BillingFrequency
    next_billing_date: datetime




class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    payment_provider: Optional[PaymentProvider] = None
    billing_frequency: Optional[BillingFrequency] = None
