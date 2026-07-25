from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.api.deps import get_db
from app.api.deps import get_current_user
from app.services.billing_service import BillingService
from app.models.project import Project
from app.services.invoice_service import InvoiceService
from app.schemas.invoice import PaginatedInvoices
from app.schemas.invoice import InvoiceDetailResponse
from fastapi import Query


router = APIRouter(prefix="/invoices", tags=["invoices"])

@router.post("/{project_id}")
def generate_invoices(
    project_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == user.id
    ).first()

    if not project:
        raise HTTPException(status_code=403, detail="Not allowed")

    # for now: full range
    period_start = datetime(2025, 1, 1)
    period_end = datetime.now(timezone.utc)

    invoices = BillingService.generate_invoices(
        db,
        project_id,
        period_start,
        period_end
    )

    return {
        "created": len(invoices)
    }

@router.get("", response_model=PaginatedInvoices)
def list_invoices(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100)
):
    return InvoiceService.list_invoices(
        db=db,
        user_id=current_user.id,
        page=page,
        page_size=page_size
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
