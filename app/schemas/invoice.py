from datetime import datetime  
from decimal import Decimal
from pydantic import BaseModel

class InvoiceSummary(BaseModel):
    external_id: str
    client_name: str
    project_name: str
    status: str
    total_amount: Decimal
    period_start: datetime
    period_end: datetime
    created_at: datetime

    model_config = {"from_attributes": True}

class InvoiceItemResponse(BaseModel):
    event_code: str
    event_name: str
    quantity: int
    unit_price: Decimal
    total: Decimal

    model_config = {"from_attributes": True}

class InvoiceDetailResponse(BaseModel):
    external_id: str
    status: str
    client_name: str
    period_start: datetime
    period_end: datetime
    total_amount: Decimal
    invoice_items: list[InvoiceItemResponse]

    model_config = {"from_attributes": True}

class PaginatedInvoices(BaseModel):
    page: int
    page_size: int
    total: int
    pages: int
    items: list[InvoiceSummary]

    model_config = {"from_attributes": True}