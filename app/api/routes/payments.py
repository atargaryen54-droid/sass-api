
from fastapi import APIRouter, status, Depends
from app.payment.schemas import CreatePaymentResponse
from app.api.deps import get_db
from sqlalchemy.orm import Session
from app.api.deps import get_current_user
from app.payment.payment_service import PaymentService



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