from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey, String
from sqlalchemy.sql import func
from app.core.database import Base


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True)

    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)

    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)

    total_amount = Column(Float, nullable=False)

    status = Column(String, default="pending")  # pending, paid, failed

    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
