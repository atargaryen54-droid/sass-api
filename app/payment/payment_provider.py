from abc import ABC, abstractmethod


class PaymentProvider(ABC):

    @abstractmethod
    def create_payment_intent(self, payment):
        pass

    # @abstractmethod
    # def retrieve_payment(self, provider_payment_id):
    #     pass

    # @abstractmethod
    # def construct_webhook_event(self, event):
    #     pass

    @abstractmethod
    def verify_webhook_signature(self, payload: bytes, signature: str,):
        pass
