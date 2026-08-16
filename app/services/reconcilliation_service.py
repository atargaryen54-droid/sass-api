
from app.payment.payment_repository import PaymentRepository
from sqlalchemy.orm import Session
from app.payment.provider_factory import PaymentProviderFactory
from fastapi import HTTPException, status
from app.payment.payment_status_service import PaymentStatusService
from app.repositories.refund_repository import RefundRepository
from app.services.refund_status_service import RefundStatusService
from app.schemas.enums import RefundStatus, PaymentStatus
from app.payment.payment_service import PaymentService
import logging


class ReconciliationService:

    @staticmethod
    def reconcile_payments(db: Session) -> None:
        payments = PaymentRepository.get_reconcilable_payments(db)

        for payment in payments:
            try:
                provider = PaymentProviderFactory.get(payment.provider)
                result = provider.get_payment_status(payment.provider_payment_id)
                provider_status = result.get("status")

                if payment.status != provider_status:
                    PaymentStatusService.transition_status(payment, provider_status)
                    if provider_status == PaymentStatus.FAILED:
                        payment.failure_reason = result.get("reason")

            except Exception as e:
                logging.error(
                    f"Failed to reconcile payment {payment.external_id}: {str(e)}",
                    exc_info=True
                )
                continue 

        db.commit()

    @staticmethod
    def reconcile_refunds(db: Session) -> None:
        refunds = RefundRepository.get_reconcilable_refunds(db)

        for refund in refunds:
            try:
                provider = PaymentProviderFactory.get(refund.provider)
                result = provider.get_refund_status(refund.provider_refund_id)

                provider_status = result.get("status")

                if refund.status != provider_status:
                    RefundStatusService.transition_status(refund, provider_status)

                    if provider_status == RefundStatus.FAILED:
                        refund.failure_reason = result.get("reason")

                    if provider_status == RefundStatus.SUCCEEDED:
                        PaymentService.mark_refunded_if_fully_refunded(db, refund.payment_id)

            except Exception as e:
                logging.error(
                    f"Failed to reconcile refund {refund.external_id}: {str(e)}",
                    exc_info=True
                )
                continue

        db.commit()

