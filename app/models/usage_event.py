from sqlalchemy import Column, Index, Integer, String, DateTime, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class UsageEvent(Base):
    __tablename__ = "usage_events"

    id = Column(Integer, primary_key=True, index=True)

    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)

    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)

    api_key_id = Column(Integer, ForeignKey("api_keys.id"), nullable=False)

    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=True)

    idempotency_key = Column(String(36), nullable=False)

    event_type_id = Column(Integer, ForeignKey("event_types.id"), nullable=False)

    quantity = Column(Integer, default=1)

    event_metadata = Column(JSON, nullable=True)

    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    
    __table_args__ = (
        UniqueConstraint("client_id", "idempotency_key", name="uq_client_idempotency"),
        Index("ix_client_idempotency", "client_id", "idempotency_key"),
    )


    event_type = relationship("EventType")


