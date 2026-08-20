from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.api.deps import get_db
from app.api.deps import get_current_user
from app.services.invoice_service import InvoiceService
from app.schemas.invoice import PaginatedInvoices
from app.schemas.invoice import InvoiceDetailResponse
from fastapi import Query
from app.schemas.invoice import InvoiceFilter
from app.tasks.scheduler_tasks import generate_due_invoices


router = APIRouter(prefix="/invoices", tags=["invoices"])


@router.get("", response_model=PaginatedInvoices)
def list_invoices(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    filters: InvoiceFilter = Depends(),
):
    return InvoiceService.list_invoices(
        db=db,
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        filters=filters
    )

@router.get("/{invoice_external_id}",response_model=InvoiceDetailResponse)
def get_invoice(invoice_external_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return InvoiceService.get_invoice_detail(
        db=db,
        user_id=current_user.id,
        invoice_external_id=invoice_external_id,
    )

@router.post("")
def generate_due_invoices_manually():
    return generate_due_invoices()

