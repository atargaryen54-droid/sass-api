from app.schemas.enums import PaymentStatus

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
            PaymentStatus.SUCCEEDED,
            PaymentStatus.FAILED # need to figure out the instance where this happens
        },

        # 3. Stripe & Bank actively processing the card
        PaymentStatus.PROCESSING: {
            PaymentStatus.SUCCEEDED, # Card accepted!
            PaymentStatus.FAILED,    # Card declined / Insufficient funds / 3DS failed
            PaymentStatus.CANCELLED, # Timed out or canceled during auth
        },

        # 4. Card was declined, but user can re-try with a new card!
        PaymentStatus.FAILED: {
            PaymentStatus.PROCESSING,# User enters a new card and hits "Pay" again
            PaymentStatus.CANCELLED, # User gives up
        },

        PaymentStatus.SUCCEEDED: set(),

        PaymentStatus.CANCELLED: set(),

    }

    @staticmethod
    def transition_status(payment, new_status: PaymentStatus):

        allowed = PaymentStatusService.ALLOWED_TRANSITIONS.get(payment.status, set())

        if new_status not in allowed:
            raise ValueError(
                f"Cannot transition from "
                f"{payment.status} to {new_status}"
            )

        payment.status = new_status