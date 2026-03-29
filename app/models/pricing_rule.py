from sqlalchemy import Column, Integer, String, Float, ForeignKey,  UniqueConstraint
from app.core.database import Base


class PricingRule(Base):
    __tablename__ = "pricing_rules"

    id = Column(Integer, primary_key=True)

    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)

    event_type = Column(String, nullable=False)

    price_per_unit = Column(Float, nullable=False)
    __table_args__ = (
    UniqueConstraint("project_id", "event_type", name="uix_project_event"),
)
