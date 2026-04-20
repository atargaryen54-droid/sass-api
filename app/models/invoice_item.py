from sqlalchemy import Column, Integer, Float, String, ForeignKey
from app.core.database import Base


class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id = Column(Integer, primary_key=True)

    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)

    event_type = Column(String, nullable=False)

    quantity = Column(Integer, nullable=False)

    unit_price = Column(Float, nullable=False)

    total = Column(Float, nullable=False)
