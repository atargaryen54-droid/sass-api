from app.schemas.enums import InvoiceStatus
from app.models.invoice import Invoice
import logging


class InvoiceStatusService:
    ALLOWED_TRANSITIONS = {
        InvoiceStatus.GENERATED: {
            InvoiceStatus.PENDING,
            InvoiceStatus.VOIDED,
        },
        InvoiceStatus.PENDING: {
            InvoiceStatus.PAID,
            InvoiceStatus.VOIDED,
        },
        InvoiceStatus.PAID:{
            InvoiceStatus.REFUNDED

        },
        
        InvoiceStatus.REFUNDED: set(),
        InvoiceStatus.VOIDED: set(),
    }

    @staticmethod
    def transition_status(invoice: Invoice, new_status: InvoiceStatus):
        if invoice.status == new_status:
            logging.info(
                f"invoice {invoice.external_id} already in status {new_status}. Skipping transition (idempotent)."
            )
            return False

        allowed = InvoiceStatusService.ALLOWED_TRANSITIONS.get(invoice.status, set())

        if new_status not in allowed:
            raise ValueError(
                f"Cannot transition from "
                f"{invoice.status} to {new_status}"
            )

        invoice.status = new_status
        return True

    