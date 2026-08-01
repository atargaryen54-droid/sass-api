from app.schemas.enums import InvoiceStatus
from app.models.invoice import Invoice


class InvoiceStatusService:
    ALLOWED_TRANSITIONS = {
        InvoiceStatus.GENERATED: {
            InvoiceStatus.PENDING,
            InvoiceStatus.VOIDED,
        },
        InvoiceStatus.PENDING: {
            InvoiceStatus.PENDING,
            InvoiceStatus.PAID,
            InvoiceStatus.FAILED,
            InvoiceStatus.VOIDED,
        },
        InvoiceStatus.FAILED: {
            InvoiceStatus.PENDING,
            InvoiceStatus.VOIDED,
        },
        InvoiceStatus.PAID: set(),
        InvoiceStatus.VOIDED: set(),
    }

    @staticmethod
    def transition_status(invoice: Invoice, new_status: InvoiceStatus):

        allowed = InvoiceStatusService.ALLOWED_TRANSITIONS.get(invoice.status, set())

        if new_status not in allowed:
            raise ValueError(
                f"Cannot transition from "
                f"{invoice.status} to {new_status}"
            )

        invoice.status = new_status

    