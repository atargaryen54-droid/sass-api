from app.schemas.enums import PaymentStatus
from app.models.payment import Payment
import logging

class PaymentStatusService:
    ALLOWED_TRANSITIONS = {

        # 1. Payment record created in DB
        PaymentStatus.CREATED: {
            PaymentStatus.INITIATED, # PaymentIntent requested
            PaymentStatus.FAILED,    # Bad payload / Stripe API connection error
            PaymentStatus.CANCELLED, # User abandoned before setup
        },

        # 2. Intent ID & client_secret sent to frontend (User is looking at card form)
        PaymentStatus.INITIATED: {
            PaymentStatus.PROCESSING,# User clicked "Pay" (Frontend submitted card)
            PaymentStatus.CANCELLED, # User navigated away / canceled checkout
            PaymentStatus.SUCCEEDED, # For testing purposes there isn't in betwenn processing
            PaymentStatus.FAILED # need to figure out the instance where this happens
        },

        # 3. Stripe & Bank actively processing the card
        PaymentStatus.PROCESSING: {
            PaymentStatus.SUCCEEDED, # Card accepted!
            PaymentStatus.FAILED,    # Card declined / Insufficient funds / 3DS failed
            PaymentStatus.CANCELLED, # Timed out or canceled during auth
        },

        PaymentStatus.SUCCEEDED:{
            PaymentStatus.REFUNDED
        },


        PaymentStatus.FAILED: set(),

        PaymentStatus.REFUNDED: set(),

        PaymentStatus.CANCELLED: set(),

    }

    @staticmethod
    def transition_status(payment:Payment, new_status: PaymentStatus):

        if payment.status == new_status:
            logging.info(
                f"Payment {payment.external_id} already in status {new_status}. Skipping transition (idempotent)."
            )
            return False

        allowed = PaymentStatusService.ALLOWED_TRANSITIONS.get(payment.status, set())

        if new_status not in allowed:
            raise ValueError(
                f"Cannot transition from "
                f"{payment.status} to {new_status}"
            )

        payment.status = new_status
        return True

    