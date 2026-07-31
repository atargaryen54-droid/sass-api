from sqlalchemy.orm import Session
from app.payment.payment_repository import PaymentRepository
import logging
from app.schemas.enums import PaymentStatus, InvoiceStatus
from app.payment.payment_status_service import PaymentStatusService
from app.services.invoice_status_service import InvoiceStatusService

class WebhookService:

    @staticmethod
    def process_stripe_event(db: Session, event,):
        event_type = event["type"]
        if event_type == "payment_intent.succeeded":

            payment_intent = event["data"]["object"]
            provider_payment_id = payment_intent["id"]

            payment = PaymentRepository.get_by_provider_payment_id(
                db,
                provider_payment_id,
            )

            if payment is None:
                logging.warning("Payment not found.")
                return
            
            if payment.status == PaymentStatus.SUCCEEDED:
                return

            PaymentStatusService.transition_status(
                payment,
                PaymentStatus.SUCCEEDED,
            )
            InvoiceStatusService.transition_status(
                payment.invoice,
                InvoiceStatus.PAID,
            )
            db.commit()
