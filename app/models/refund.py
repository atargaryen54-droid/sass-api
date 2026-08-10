import secrets

from sqlalchemy import Integer, String, DateTime, Column, ForeignKey, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
from app.schemas.enums import PaymentProvider, RefundStatus


def generate_short_id():
    return secrets.token_urlsafe(9)


class Refund(Base):
    __tablename__ = "refunds"

    id = Column(Integer, primary_key=True)   

    external_id = Column(String, unique=True, nullable=False, default=generate_short_id)   

    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=False)

    provider = Column(String, nullable=False, default=PaymentProvider.STRIPE)

    provider_refund_id = Column(String, nullable=True)

    amount = Column(Numeric(12, 2), nullable=False)

    currency = Column(String(3), nullable=False, default="USD")

    status = Column(String, nullable=False, default=RefundStatus.CREATED)

    reason = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    update_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    
    payment = relationship("Payment", back_populates="refunds")


