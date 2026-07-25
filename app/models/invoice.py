import secrets
from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

def generate_short_id():
    return secrets.token_urlsafe(9)
class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True)

    external_id = Column(String, unique=True, nullable=False, default=generate_short_id)

    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)

    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)

    total_amount = Column(Float, nullable=False)

    status = Column(String, default="pending")  # pending, paid, failed

    period_start = Column(DateTime, nullable=False)
    
    period_end = Column(DateTime, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


    client = relationship("Client")
    project = relationship("Project")
    invoice_items = relationship("InvoiceItem", back_populates="invoice")

    @property
    def client_name(self) -> str:
        return self.client.name if self.client else ""

    @property
    def project_name(self) -> str:
        return self.project.name if self.project else ""