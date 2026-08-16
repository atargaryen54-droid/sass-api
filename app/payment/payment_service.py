
from sqlalchemy.orm import Session
from app.payment.provider_factory import PaymentProviderFactory
from app.repositories.invoice_repository import InvoiceRepository
from fastapi import HTTPException, status
from app.schemas.enums import PaymentStatus, InvoiceStatus, RefundStatus
from app.payment.payment_repository import PaymentRepository
from app.payment.payment_status_service import PaymentStatusService
from app.services.invoice_status_service import InvoiceStatusService
from app.payment.schemas import PaymentFilter
from app.models.payment  import Payment
from app.repositories.refund_repository import RefundRepository
import logging



class PaymentService:

    @staticmethod
    def create_payment(db: Session, user_id: int, invoice_external_id: str,):
        invoice = InvoiceRepository.get_detail(
            db=db,
            user_id=user_id,
            invoice_external_id=invoice_external_id,
        )

        if not invoice:
            raise HTTPException(
                status_code=404,
                detail="Invoice not found.",
            )
        if invoice.status in (InvoiceStatus.VOIDED, InvoiceStatus.PAID ):
            raise HTTPException(
                status_code = status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail = f"Payment can't be created for invoice with status '{invoice.status}'"
            )
       
        payment = PaymentRepository.create(
            db=db,
            invoice_id=invoice.id,  
            provider=invoice.project.payment_provider,
            amount=invoice.total_amount,
            currency="USD",
        )

        provider = PaymentProviderFactory.get(payment.provider)
        

        try:
            result = provider.create_payment_intent(payment)

        except Exception as e:
            PaymentStatusService.transition_status(
                payment,
                PaymentStatus.FAILED,
            )

            payment.failure_reason = str(e)

            db.commit()

            raise
        
        payment.provider_payment_id = result.provider_payment_id

        PaymentStatusService.transition_status(
            payment,
            PaymentStatus.INITIATED,
        )
        
        if invoice.status == InvoiceStatus.GENERATED:
            InvoiceStatusService.transition_status(
                invoice,
                InvoiceStatus.PENDING,
            )

        db.commit()
        db.refresh(payment)

        return {
            "payment_external_id": payment.external_id,
            "client_secret": result.client_secret,
        }

    @staticmethod
    def list_payments(
        db:Session,
        user_id: int,
        page: int,
        page_size: int,
        filters: PaymentFilter
    ):
        return PaymentRepository.list_by_user(
            db=db, 
            user_id=user_id,
            page=page,
            page_size=page_size,
            filters=filters
            )
       
    @staticmethod
    def retry_payment(db: Session, user_id: int, invoice_external_id: str):
        invoice = InvoiceRepository.get_detail(db, user_id, invoice_external_id)
        if not invoice:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found"
            )

        # Fetch the latest payment attempt for this invoice
        latest_payment = (
            db.query(Payment)
            .filter(Payment.invoice_id == invoice.id)
            .order_by(Payment.created_at.desc())
            .first()
        )

        # SingleGuard Condition: Retry ONLY allowed if invoice is PENDING and last payment FAILED
        is_pending = invoice.status == InvoiceStatus.PENDING
        has_failed_payment = (
            latest_payment and latest_payment.status == PaymentStatus.FAILED
        )

        if not (is_pending and has_failed_payment):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Payment for invoice '{invoice_external_id}' cannot be retried. "
                f"(Invoice status: {invoice.status}, Latest payment: {latest_payment.status if latest_payment else 'none'})",
            )

        return PaymentService.create_payment(db, user_id, invoice_external_id)

    @staticmethod
    def mark_refunded_if_fully_refunded(db, payment_id):

        payment = PaymentRepository.get_by_id(db, payment_id)

        refunds = RefundRepository.list_by_payment(db=db, payment_id=payment_id)
        refunded_amount = sum(
            refund.amount
            for refund in refunds
            if refund.status == RefundStatus.SUCCEEDED
        )

        if refunded_amount >= payment.amount:
            PaymentStatusService.transition_status(payment, PaymentStatus.REFUNDED)
            InvoiceStatusService.transition_status(payment.invoice, InvoiceStatus.REFUNDED )
            logging.info(f"payment {payment.external_id} fully refunded")



            
