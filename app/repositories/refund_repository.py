from sqlalchemy.orm import Session
from app.models import Refund, Payment
from app.schemas.enums import RefundStatus


class RefundRepository:

    @staticmethod
    def create(
        db:Session, 
        payment_id: int,
        provider:str, 
        amount:float, 
        currency:str,
        reason:str | None=None):

        refund = Refund(
            payment_id = payment_id,
            provider = provider,
            amount = amount,
            currency = currency,
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
        return db.query(Refund).filter(Refund.provider_refund_id == provider_refund_id).first()

    
    @staticmethod
    def get_reconcilable_refunds(db:Session):
        return(
            db.query(Refund)
            .filter(
                Refund.status.in_([
                    RefundStatus.PENDING
                ])         
            ).all()
        )


    


