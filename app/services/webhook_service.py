from sqlalchemy.orm import Session
from app.payment.payment_repository import PaymentRepository
import logging
from app.schemas.enums import PaymentStatus, InvoiceStatus
from app.payment.payment_status_service import PaymentStatusService
from app.services.invoice_status_service import InvoiceStatusService
from app.repositories.processed_webhook_repository import ProcessedWebhookRepository

class WebhookService:

    @staticmethod
    def process_stripe_event(db: Session, event,):

        already_processed = ProcessedWebhookRepository.exists(
            db=db,
            provider="stripe",
            event_id=event["id"],
        )

        if already_processed:
            logging.info(f"Event {event['id']} has already been processed.")
            return

        event_type = event["type"]

        if event_type == "payment_intent.succeeded":
            WebhookService.handle_payment_succeeded(db, event)

        elif event_type == "payment_intent.payment_failed":
            WebhookService.handle_payment_failed(db, event)

        elif event_type == "payment_intent.canceled":
            WebhookService.handle_payment_canceled(db, event)

    @staticmethod
    def get_payment_from_event(db: Session, event):

        payment_intent = event["data"]["object"]
        provider_payment_id = payment_intent["id"]

        payment = PaymentRepository.get_by_provider_payment_id(
            db,
            provider_payment_id,
        )
        return payment

    @staticmethod
    def create_processed_webhook_record(db: Session, provider: str, event_id: str):
        return ProcessedWebhookRepository.create(
            db=db,
            provider=provider,
            event_id=event_id,
        )

    @staticmethod
    def handle_payment_succeeded(db: Session, event):

        payment = WebhookService.get_payment_from_event(db, event)

        if payment is None:
            logging.warning("Payment not found.")
            return

        if payment.status == PaymentStatus.SUCCEEDED: 
            logging.info(f"Payment {payment.id} already marked as SUCCEEDED.")
            return

        PaymentStatusService.transition_status(
            payment,
            PaymentStatus.SUCCEEDED,
        )
        InvoiceStatusService.transition_status(
            payment.invoice,
            InvoiceStatus.PAID,
        )

        WebhookService.create_processed_webhook_record(db, payment.provider, event["id"])
        logging.info(f"Payment {payment.external_id} and Invoice {payment.invoice.external_id} marked as PAID.")

        db.commit()


    @staticmethod
    def handle_payment_failed(db: Session, event):

        payment = WebhookService.get_payment_from_event(db, event)

        if payment is None:
            logging.warning("Payment not found.")
            return
        
        payment_intent = event["data"]["object"]
        last_error = getattr(payment_intent, "last_payment_error", None)
        new_reason = getattr(last_error, "message", "Payment failed") if last_error else "Payment failed"

        payment.failure_reason = new_reason

        if payment.status == PaymentStatus.FAILED:
            db.commit()
            logging.info(f"Updated failure reason for already-failed payment {payment.external_id}")
            return

        PaymentStatusService.transition_status(
            payment,
            PaymentStatus.FAILED,
        )

        WebhookService.create_processed_webhook_record(db, payment.provider, event["id"])
        logging.info(f"Payment {payment.id} marked as FAILED.")

        db.commit()


    @staticmethod
    def handle_payment_canceled(db: Session, event):
        
        payment = WebhookService.get_payment_from_event(db, event)

        if payment is None:
            logging.warning("Payment not found.")
            return

        PaymentStatusService.transition_status(
            payment,
            PaymentStatus.CANCELLED,
        )

        WebhookService.create_processed_webhook_record(db, payment.provider, event["id"])
        logging.info(f"Payment {payment.external_id} marked as CANCELLED.")

        db.commit()


