from sqlalchemy.orm import Session
from app.payment.payment_repository import PaymentRepository
from fastapi import HTTPException, status
import logging
from app.schemas.enums import PaymentStatus, RefundStatus
from app.repositories.refund_repository import RefundRepository
from app.payment.provider_factory import PaymentProviderFactory
from app.services.refund_status_service import RefundStatusService


class RefundService:
    def create_refund(
        db:Session,
        user_id: int,
        payment_external_id: str,
        requested_amount: float | None=None,
        reason: str | None=None):

        payment = PaymentRepository.get_by_external_id(
            db=db,
            user_id=user_id,
            payment_external_id=payment_external_id
        )

        if not payment:
            raise HTTPException(
                status_code = status.HTTP_404_NOT_FOUND,
                detail = "payment not found"
            )
        if payment.status == PaymentStatus.REFUNDED:
            raise HTTPException(
                status_code = status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail = "Payment already fully refunded"
            )


        
        if payment.status != PaymentStatus.SUCCEEDED:
            raise HTTPException(
                status_code = status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail = "Only successful payments can be refunded"
            )

        refunds = RefundRepository.list_by_payment(db=db, payment_id=payment.id)
        refunded_amount = sum(
            refund.amount
            for refund in refunds
            if refund.status == RefundStatus.SUCCEEDED
        )
        remaining_amount = payment.amount - refunded_amount
        
        refund_amount = (
            remaining_amount
            if requested_amount is None
            else requested_amount
        )

        if refund_amount <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Refund amount must be greater than zero.",
            )
        if refund_amount > remaining_amount:
            raise HTTPException(
                status_code= status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Refund amount {refund_amount} exceeds the remaining refundable amount {remaining_amount}",
            )

        refund = RefundRepository.create(
            db=db,
            payment_id=payment.id,
            provider=payment.provider,
            amount=refund_amount,
            currency=payment.currency,
            reason=reason,
        )

        provider = PaymentProviderFactory.get(payment.provider)

        try:
            result = provider.create_refund(payment=payment,amount=refund.amount,)

        except Exception:
            db.rollback()
            raise

        refund.provider_refund_id = result.get("provider_refund_id", set())

        RefundStatusService.transition_status(
            refund,
            RefundStatus.PENDING,
        )

        db.commit()
        db.refresh(refund)

        return {
            "refund_external_id": refund.external_id,
            "status": refund.status
        }







        




