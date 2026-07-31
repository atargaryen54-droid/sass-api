from app.schemas.enums import PaymentProvider
from app.providers.stripe_provider import StripeProvider


class PaymentProviderFactory:

    @staticmethod
    def get(provider: PaymentProvider):
        if provider == PaymentProvider.STRIPE:
            return StripeProvider()
        else:
            raise ValueError(f"Unsupported payment provider: {provider}")