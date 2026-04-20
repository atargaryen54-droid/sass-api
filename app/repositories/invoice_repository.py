from sqlalchemy.orm import Session
from app.models.invoice import Invoice
from app.models.invoice_item import InvoiceItem


class InvoiceRepository:

    @staticmethod
    def create_invoice(
        db: Session,
        project_id: int,
        client_id: int,
        total_amount: float,
        period_start,
        period_end,
        items: list
    ):

        invoice = Invoice(
            project_id=project_id,
            client_id=client_id,
            total_amount=total_amount,
            period_start=period_start,
            period_end=period_end
        )

        db.add(invoice)
        db.flush()  # get invoice.id before commit

        for item in items:
            invoice_item = InvoiceItem(
                invoice_id=invoice.id,
                event_type=item["event_type"],
                quantity=item["quantity"],
                unit_price=item["unit_price"],
                total=item["total"]
            )
            db.add(invoice_item)

        db.commit()
        db.refresh(invoice)

        return invoice
