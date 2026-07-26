
from enum import Enum


class InvoiceStatus(str, Enum):
    GENERATED = "generated"
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    VOIDED = "voided"