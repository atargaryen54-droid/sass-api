
from sqlalchemy.orm import Session
from app.payment.provider_factory import PaymentProviderFactory
from app.repositories.invoice_repository import InvoiceRepository
from fastapi import HTTPException
from app.schemas.enums import PaymentProvider, PaymentStatus, InvoiceStatus
from app.payment.payment_repository import PaymentRepository
from app.payment.payment_status_service import PaymentStatusService
from app.services.invoice_status_service import InvoiceStatusService


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