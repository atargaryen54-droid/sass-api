
from enum import Enum


class InvoiceStatus(str, Enum):

    GENERATED = "generated"

    PENDING = "pending"

    PAID = "paid"

    FAILED = "failed"

    VOIDED = "voided"

class PaymentStatus(str, Enum):

    CREATED = "created"

    INITIATED = "initiated"

    PROCESSING = "processing"

    SUCCEEDED = "succeeded"

    FAILED = "failed"

    CANCELLED = "cancelled"

class PaymentProvider(str, Enum):
    
    STRIPE = "stripe"

    CHAPA = "chapa"

    PAYPAL = "paypal"