from app.schemas.enums import RefundStatus

class RefundStatusService:
    ALLOWED_TRANSITIONS = {

        # 1. Refund record created in DB
        RefundStatus.CREATED: {
            RefundStatus.PENDING, 
            RefundStatus.FAILED,    
            RefundStatus.CANCELLED, 
        },

        # 2. Refund id is received from provider
        RefundStatus.PENDING: {

            RefundStatus.CANCELLED, 
            RefundStatus.SUCCEEDED,
            RefundStatus.FAILED 
        },

        # 3 Refund failed due to some reason
        RefundStatus.FAILED: {
            RefundStatus.PENDING,
            RefundStatus.CANCELLED, 
        },

        RefundStatus.SUCCEEDED: set(),

        RefundStatus.CANCELLED: set(),

    }

    @staticmethod
    def transition_status(refund, new_status: RefundStatus):

        allowed = RefundStatusService.ALLOWED_TRANSITIONS.get(refund.status, set())

        if new_status not in allowed:
            raise ValueError(
                f"Cannot transition from "
                f"{refund.status} to {new_status}"
            )

        refund.status = new_status