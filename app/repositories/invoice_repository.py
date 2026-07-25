from sqlalchemy.orm import Session, joinedload
from app.models.invoice import Invoice
from app.models.invoice_item import InvoiceItem
from app.models.client import Client
from app.models.project import Project
import math


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
                event_type_id=item["event_type_id"],
                quantity=item["quantity"],
                unit_price=item["unit_price"],
                total=item["total"]
            )
            db.add(invoice_item)

        return invoice

    @staticmethod
    def list_by_user(db: Session, user_id: int, page: int, page_size: int):
        offset = (page - 1) * page_size
        query = (
            db.query(Invoice)
            .join(Client, Invoice.client_id == Client.id)
            .join(Project, Client.project_id == Project.id)
            .filter(Project.user_id == user_id)
            .order_by(Invoice.created_at.desc())
        )
        total_count = query.count()

        invoices = query.offset(offset).limit(page_size).all()

        pages = math.ceil(total_count / page_size)

        return {
            "page": page,
            "page_size": page_size,
            "total": total_count,
            "pages": pages,
            "items": invoices,
        }


    @staticmethod
    def get_detail(db: Session, user_id: int, invoice_external_id: str,):
        return (
            db.query(Invoice)
            .join(Client, Invoice.client_id == Client.id)
            .join(Project, Client.project_id == Project.id)
            .options(
                joinedload(Invoice.client),
                joinedload(Invoice.invoice_items)
                    .joinedload(InvoiceItem.event_type)
            )
            .filter(
                Invoice.external_id == invoice_external_id,
                Project.user_id == user_id,
            )
            .first()
        )
