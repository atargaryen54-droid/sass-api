from sqlalchemy import Column, Integer, Float, String, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id = Column(Integer, primary_key=True)

    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)

    event_type_id = Column(Integer, ForeignKey("event_types.id"), nullable=False)

    quantity = Column(Integer, nullable=False)

    unit_price = Column(Float, nullable=False)

    total = Column(Float, nullable=False)


    invoice = relationship("Invoice", back_populates="invoice_items")

    event_type = relationship("EventType")


    @property
    def event_code(self) -> str:
        return self.event_type.event_code if self.event_type else ""

    @property
    def event_name(self) -> str:
        return self.event_type.name if self.event_type else ""






