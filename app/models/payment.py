from sqlalchemy.orm import relationship
from app.core.database import Base
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Numeric, Text, JSON
from sqlalchemy.sql import func
from app.schemas.enums import PaymentStatus, PaymentProvider
import secrets

def generate_short_id():
    return secrets.token_urlsafe(9)
class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True)

    external_id = Column(String, unique=True, nullable=False, default=generate_short_id)

    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)

    provider = Column(String, nullable=False, default=PaymentProvider.STRIPE)

    provider_payment_id = Column(String, nullable=True)

    amount = Column(Numeric(12, 2), nullable=False)

    currency = Column(String(3), nullable=False, default="USD")

    status = Column(String, nullable=False, default=PaymentStatus.CREATED)

    failure_reason = Column(Text, nullable=True)

    payment_metadata = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


    invoice = relationship("Invoice", back_populates="payments")
