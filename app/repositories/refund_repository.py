from sqlalchemy.orm import Session
from app.models import Refund, Payment


class RefundRepository:

    @staticmethod
    def create(db:Session, provider:str, amount:float, status:str, reason:str | None=None):

        refund = Refund(
            provider = provider,
            amount = amount,
            status = status,
            reason = reason
        )
        db.add(refund)
        db.flush()

        return refund

    @staticmethod
    def list_by_payment(db:Session, payment_id:str):
        return (
            db.query(Refund)
            .filter(Refund.payment_id == payment_id)
            .all()
        )

    @staticmethod
    def get_by_provider_id(db:Session, provider_refund_id:str):
        return db.query(Refund).filter(Refund.provider_refund_id == provider_refund_id)

    


