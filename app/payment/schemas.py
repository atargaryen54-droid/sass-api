from pydantic import BaseModel, ConfigDict
from datetime import datetime
from app.schemas.enums import PaymentStatus

class PaymentIntentResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    provider_payment_id: str
    client_secret: str
    status: str
    
class CreatePaymentResponse(BaseModel):
    payment_external_id: str
    client_secret: str

class PaymentSummary(BaseModel):
    external_id: str
    invoice_external_id: str
    client_external_id: str
    amount: float
    currency: str
    status: str
    provider: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PaginatedPayments(BaseModel):
    page: int
    page_size: int
    total: int
    pages: int
    items: list[PaymentSummary]

    model_config = {"from_attributes": True}

class PaymentFilter(BaseModel):
    project_ext_id: str |None = None
    client_ext_id: str |None = None
    status: PaymentStatus |None = None
    period_start: datetime |None = None
    period_end: datetime |None = None   

    model_config = {"from_attributes": True}