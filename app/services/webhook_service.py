from sqlalchemy.orm import Session
from app.payment.payment_repository import PaymentRepository
import logging
from app.schemas.enums import PaymentStatus, InvoiceStatus, RefundStatus
from app.payment.payment_status_service import PaymentStatusService
from app.services.invoice_status_service import InvoiceStatusService
from app.repositories.processed_webhook_repository import ProcessedWebhookRepository
from app.repositories.refund_repository import RefundRepository
from app.services.refund_status_service import RefundStatusService
from app.payment.payment_service import PaymentService

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
        elif event_type == "refund.updated":
            WebhookService.handle_refund_updated(db, event)

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
    def get_refund_from_event(db: Session, event):
         refund_intent = event["data"]["object"]
         provider_refund_id = refund_intent["id"]

         refund = RefundRepository.get_by_provider_id(
             db,
             provider_refund_id
         )
         return refund


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
        reason_of_failure = getattr(last_error, "message", "Payment failed") if last_error else "Payment failed"

        payment.failure_reason = reason_of_failure

        PaymentStatusService.transition_status(
            payment,
            PaymentStatus.FAILED,
        )

        WebhookService.create_processed_webhook_record(db, payment.provider, event["id"])
        logging.info(f"Payment {payment.external_id} marked as FAILED.")

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

    @staticmethod
    def handle_refund_updated(db: Session, event):
        refund = WebhookService.get_refund_from_event(db, event)

        if not refund:
            logging.warning("refund not found")
            return
        
        refund_object = event["data"]["object"]
        stripe_status = refund_object["status"]

        if stripe_status == "succeeded":
             status_change = RefundStatusService.transition_status(
                        refund,
                        RefundStatus.SUCCEEDED,
                    )
             logging.info(f"refund {refund.external_id} marked as successfully processed.")
             if status_change:
                PaymentService.mark_refunded_if_fully_refunded(db, refund.payment_id)

        elif stripe_status == "failed":
            RefundStatusService.transition_status(
                        refund,
                        RefundStatus.FAILED,
                    )
            refund.failure_reason = refund_object.get("failure_reason", "unknown")
            logging.info(f"refund {refund.external_id} marked as failed. Reason: {refund.failure_reason}")

        elif stripe_status == "cancelled":
             RefundStatusService.transition_status(
                        refund,
                        RefundStatus.CANCELLED,
                    )
             logging.info(f"refund {refund.external_id} marked as cancelled")

        else:
            logging.info(
                f"Refund {refund.external_id} received unhandled status '{stripe_status}'."
            )
            return

        WebhookService.create_processed_webhook_record(db, refund.provider, event["id"])
        db.commit()
             
            






