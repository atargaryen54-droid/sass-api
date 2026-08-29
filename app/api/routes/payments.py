
from fastapi import APIRouter, status, Depends, status
from app.payment.schemas import CreatePaymentResponse
from app.api.deps import get_db
from sqlalchemy.orm import Session
from app.api.deps import get_current_user
from app.payment.payment_service import PaymentService
from fastapi import Query
from app.payment.schemas import PaginatedPayments, PaymentFilter
from app.schemas.refund import RefundCreate
from app.services.refund_service import RefundService
from app.tasks.scheduler_tasks import run_reconciliation


router = APIRouter(prefix="/payments", tags=["payments"])

@router.post(
    "/{invoice_external_id}",
    response_model=CreatePaymentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_payment(
    invoice_external_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return PaymentService.create_payment(
        db=db,
        user_id=current_user.id,
        invoice_external_id=invoice_external_id,
    )

@router.get("", response_model=PaginatedPayments)
def list_payments(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    filters: PaymentFilter = Depends(),
):
    return PaymentService.list_payments(
        db=db,
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        filters=filters
    )

@router.post(
    "/retry/{invoice_external_id}",
    response_model=CreatePaymentResponse,
    status_code=status.HTTP_201_CREATED,
    )
def retry_payment(
    invoice_external_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    return PaymentService.retry_payment(
        db = db,
        user_id = current_user.id,
        invoice_external_id = invoice_external_id
    )

@router.post(
    "/{payment_external_id}/refunds",
    status_code=status.HTTP_201_CREATED
)
def create_refund(
    payment_external_id: str,
    payload: RefundCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    return RefundService.create_refund(
        db=db,
        user_id=current_user.id,
        payment_external_id = payment_external_id,
        requested_amount = payload.amount,
        reason = payload.reason
    )

@router.post("")
def reconcile_manually():
    run_reconciliation()
    return{
        "status": "reconciliation completed"
    }
