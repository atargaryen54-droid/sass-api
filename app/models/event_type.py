from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
import secrets



def generate_short_id():
    return secrets.token_urlsafe(9)


class EventType(Base):
    __tablename__ = "event_types"

    id = Column(Integer, primary_key=True, index=True)

    external_id = Column(String, unique=True, nullable=True, default=generate_short_id)

    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)

    name = Column(String, nullable=True)

    event_code = Column(String, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    pricing_rule = relationship("PricingRule", back_populates="event_type", uselist=False)


    __table_args__ = (
        UniqueConstraint("project_id", "event_code", name="uq_project_event_code"),
    )