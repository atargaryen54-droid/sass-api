import stripe
import logging
from app.core.config import settings
from app.payment.payment_provider import PaymentProvider
from app.payment.schemas import PaymentIntentResult
from app.schemas.enums import PaymentStatus, RefundStatus

stripe.api_key = settings.stripe_secret_key

class StripeProvider(PaymentProvider):

    @staticmethod
    def _to_stripe_amount(amount):
        return int(amount * 100)

    def create_payment_intent(self, payment):
        intent = stripe.PaymentIntent.create(
            amount=self._to_stripe_amount(payment.amount),
            currency=payment.currency.lower(),
            metadata={
                "payment_external_id": payment.external_id,
                "invoice_external_id": payment.invoice.external_id,
            },
            automatic_payment_methods={
                "enabled": True
            },
        )

        return PaymentIntentResult(
            provider_payment_id=intent.id,
            client_secret=intent.client_secret,
            status=intent.status,
        )

    
    def verify_webhook_signature(self, payload: bytes, signature: str,):
        return stripe.Webhook.construct_event(
            payload=payload,
            sig_header=signature,
            secret=settings.stripe_webhook_secret,
        )

    def create_refund(self, payment, amount):
        refund = stripe.Refund.create(
            payment_intent=payment.provider_payment_id,
            amount=self._to_stripe_amount(amount),
        )
        return {
            "provider_refund_id" : refund.id,
            "status" : refund.status
        }

    def get_payment_status(self, provider_payment_id):
            intent = stripe.PaymentIntent.retrieve(provider_payment_id)

            status_mapping = {
                "succeeded": PaymentStatus.SUCCEEDED,
                "requires_payment_method": PaymentStatus.FAILED,
                "canceled": PaymentStatus.CANCELLED,
                "processing": PaymentStatus.PROCESSING,
                "requires_action": PaymentStatus.PROCESSING,
                "requires_confirmation": PaymentStatus.INITIATED,
                "requires_capture": PaymentStatus.PROCESSING,
            }
            mapped_status = status_mapping.get(intent.status)

            if mapped_status is None:
                logging.warning(
                    f"Unhandled Stripe status encountered: '{intent.status}' for intent {intent.id}. "
                    f"Defaulting to INITIATED."
                )
                mapped_status = PaymentStatus.INITIATED

            reason = (
                (intent.last_payment_error.get("decline_code") or intent.last_payment_error.get("code") or intent.last_payment_error.get("message"))
                if intent.last_payment_error
                else None
            )
            
            return {
                "status": mapped_status,
                "reason": reason
            }

    def get_refund_status(self, provider_refund_id):
        intent = stripe.Refund.retrieve(provider_refund_id)
         
        status_mapping = {
            "succeeded": RefundStatus.SUCCEEDED,
            "canceled": RefundStatus.CANCELLED,
            "pending": RefundStatus.PENDING,
            "requires_action": RefundStatus.PENDING,
            "failed": RefundStatus.FAILED
        }
        mapped_status = status_mapping.get(intent.status)

        if mapped_status is None:
            logging.warning(
                f"Unhandled Stripe status encountered: '{intent.status}' for intent {intent.id}. "
                f"Defaulting to PENDING."
            )
            mapped_status = RefundStatus.PENDING

        reason = getattr(intent, "failure_reason", None)

        return {
            "status": mapped_status,
            "reason": reason
        }
        


    
    





    # @staticmethod
    # def retrieve_payment(*args, **kwargs):
    #     pass

    # @staticmethod
    # def cancel_payment(*args, **kwargs):
    #     pass

    # @staticmethod
    # def construct_webhook_event(*args, **kwargs):
    #         pass
    
  