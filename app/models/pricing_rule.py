from sqlalchemy import Column, Integer, String, Float, ForeignKey,  UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.ext.associationproxy import association_proxy
from app.core.database import Base
import secrets


def generate_short_id():
    return secrets.token_urlsafe(9)

class PricingRule(Base):
    __tablename__ = "pricing_rules"

    id = Column(Integer, primary_key=True)

    external_id = Column(String, unique=True, nullable=True, default=generate_short_id)

    event_type_id = Column(Integer, ForeignKey("event_types.id"), nullable=False, unique=True)

    price_per_unit = Column(Float, nullable=False)
    
    event_type = relationship("EventType", back_populates="pricing_rule")
    event_code = association_proxy("event_type", "event_code")


