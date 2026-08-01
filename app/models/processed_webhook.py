from sqlalchemy import Integer, String, DateTime, Column, UniqueConstraint
from sqlalchemy.sql import func
from app.core.database import Base


class ProcessedWebhook(Base):
    __tablename__ = "processed_webhooks"

    id = Column(Integer, primary_key=True)

    provider = Column(String, nullable=False)

    event_id = Column(String, nullable=False)

    processed_at = Column(DateTime(timezone=True), server_default=func.now())


    __table_args__ = (
        UniqueConstraint("provider", "event_id", name="uq_provider_event"),
    )




