
from enum import Enum


class InvoiceStatus(str, Enum):

    GENERATED = "generated"

    PENDING = "pending"

    PAID = "paid"

    VOIDED = "voided"

    REFUNDED = "refunded"

class PaymentStatus(str, Enum):

    CREATED = "created"

    INITIATED = "initiated"

    PROCESSING = "processing"

    SUCCEEDED = "succeeded"

    FAILED = "failed"

    CANCELLED = "cancelled"

    REFUNDED = "refunded"

class PaymentProvider(str, Enum):
    
    STRIPE = "stripe"

    CHAPA = "chapa"

    PAYPAL = "paypal"

class BillingFrequency(str, Enum):

    DAILY = "daily"

    WEEKLY = "weekly"
    
    MONTHLY = "monthly"

class RefundStatus(str, Enum):

    CREATED = "created"

    PENDING = "pending"

    SUCCEEDED = "succeeded"

    FAILED = "failed"

    CANCELLED = "cancelled"