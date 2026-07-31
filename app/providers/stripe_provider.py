import stripe
from app.core.config import settings
from app.payment.payment_provider import PaymentProvider
from app.payment.schemas import PaymentIntentResult

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



    # @staticmethod
    # def retrieve_payment(*args, **kwargs):
    #     pass

    # @staticmethod
    # def cancel_payment(*args, **kwargs):
    #     pass

    # @staticmethod
    # def construct_webhook_event(*args, **kwargs):
    #         pass
    
  