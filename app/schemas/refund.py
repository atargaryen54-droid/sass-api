from pydantic import BaseModel, Field
from typing import Optional


class RefundCreate(BaseModel):
    amount: Optional[float] = Field(
        default=None,
        gt=0,
        description="Amount to refund. If omitted, full payment amount is refunded.",
    )
    reason: Optional[str] = Field(
        default=None, max_length=255, description="Optional reason for refund."
    )
