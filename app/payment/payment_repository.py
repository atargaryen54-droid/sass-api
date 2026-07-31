from sqlalchemy.orm import Session
from app.models.payment import Payment


class PaymentRepository:

    @staticmethod
    def create(db: Session, invoice_id: int, provider: str, amount: float, currency: str):

        payment = Payment(
            invoice_id=invoice_id,
            provider=provider,
            amount=amount,
            currency=currency
        )

        db.add(payment)
        db.flush()

        return payment

    @staticmethod 
    def get_by_provider_payment_id(db: Session, provider_payment_id: str):
        return (
            db.query(Payment)
            .filter(
                Payment.provider_payment_id ==
                provider_payment_id
            )
            .first()
        )
