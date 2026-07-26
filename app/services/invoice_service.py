from sqlalchemy.orm import Session
from app.repositories.invoice_repository import InvoiceRepository
from fastapi import HTTPException
from app.schemas.invoice import InvoiceFilter

class InvoiceService:

    @staticmethod
    def list_invoices(
        db: Session, 
        user_id: int,
        page: int, 
        page_size: int, 
        filters: InvoiceFilter):

        return InvoiceRepository.list_by_user(db, user_id, page, page_size, filters)


    @staticmethod
    def get_invoice_detail(db: Session, user_id: int, invoice_external_id: str):
        invoice = InvoiceRepository.get_detail(
                db,
                user_id,
                invoice_external_id,
            )

        if not invoice:
            raise HTTPException(
                status_code=404,
                detail="Invoice not found."
            )

        return invoice