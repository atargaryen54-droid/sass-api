from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

class EventType(Base):
    __tablename__ = "event_types"

    id = Column(Integer, primary_key=True, index=True)

    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)

    name = Column(String, nullable=True)

    event_code = Column(String, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    pricing_rule = relationship("PricingRule", back_populates="event_type", uselist=False)
