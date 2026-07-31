from pydantic import BaseModel


class PaymentIntentResult(BaseModel):
    provider_payment_id: str
    client_secret: str
    status: str


    class Config:
        from_attributes = True

class CreatePaymentResponse(BaseModel):
    payment_external_id: str
    client_secret: str
