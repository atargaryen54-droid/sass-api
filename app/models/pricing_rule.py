from sqlalchemy import Column, Integer, String, Float, ForeignKey,  UniqueConstraint
from sqlalchemy.orm import relationship
from app.core.database import Base


class PricingRule(Base):
    __tablename__ = "pricing_rules"

    id = Column(Integer, primary_key=True)

    event_type_id = Column(Integer, ForeignKey("event_types.id"), nullable=False, unique=True)

    price_per_unit = Column(Float, nullable=False)

    
    event_type = relationship("EventType", back_populates="pricing_rule")


