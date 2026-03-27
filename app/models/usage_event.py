from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func
from app.core.database import Base


class UsageEvent(Base):
    __tablename__ = "usage_events"

    id = Column(Integer, primary_key=True, index=True)

    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)

    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)

    api_key_id = Column(Integer, ForeignKey("api_keys.id"), nullable=False)

    event_type = Column(String, nullable=False)

    quantity = Column(Integer, default=1)

    event_metadata = Column(JSON, nullable=True)

    timestamp = Column(DateTime(timezone=True), server_default=func.now())
