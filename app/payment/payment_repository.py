from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.payment import Payment
from app.payment.schemas import PaymentFilter
from app.models import Project, Client, Invoice
from app.schemas.enums import PaymentStatus
import math


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
    def get_by_external_id(db: Session, user_id: int, payment_external_id: str):
        return (
            db.query(Payment)
            .join(Invoice, Payment.invoice_id == Invoice.id)
            .join(Client, Invoice.client_id == Client.id)
            .join(Project, Client.project_id == Project.id)
            .filter(
                Project.user_id == user_id,
                Payment.external_id == payment_external_id
            )
            .first()
        )
    















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

    @staticmethod
    def list_by_user(
        db: Session,
        user_id: int,
        page: int,
        page_size: int,
        filters: PaymentFilter,
    ):
        offset = (page - 1) * page_size

        base_query = (
            db.query(Payment)
            .join(Invoice, Payment.invoice_id == Invoice.id)
            .join(Client, Invoice.client_id == Client.id)
            .join(Project, Client.project_id == Project.id)
            .filter(Project.user_id == user_id)
        )

        if filters.project_ext_id:
            base_query = base_query.filter(
                Project.external_id == filters.project_ext_id
            )

        if filters.client_ext_id:
            base_query = base_query.filter(
                Client.external_id == filters.client_ext_id
            )

        if filters.status:
            status_val = (
                filters.status.value
                if isinstance(filters.status, PaymentStatus)
                else filters.status
            )
            base_query = base_query.filter(Payment.status == status_val)

        if filters.period_start:
            base_query = base_query.filter(
                Payment.created_at >= filters.period_start
            )

        if filters.period_end:
            base_query = base_query.filter(
                Payment.created_at <= filters.period_end
            )

        total_count = base_query.with_entities(
            func.count(Payment.id)
        ).scalar() or 0

    
        items_query = base_query.with_entities(
            Payment.external_id.label("external_id"),
            Invoice.external_id.label("invoice_external_id"),
            Client.external_id.label("client_external_id"),
            Payment.amount.label("amount"),
            Payment.currency.label("currency"),
            Payment.status.label("status"),
            Payment.provider.label("provider"),
            Payment.created_at.label("created_at"),
        )

        payments = (
            items_query.order_by(Payment.created_at.desc())
            .offset(offset)
            .limit(page_size)
            .all()
        )

        pages = math.ceil(total_count / page_size) if page_size > 0 else 0

        return {
            "page": page,
            "page_size": page_size,
            "total": total_count,
            "pages": pages,
            "items": payments,  
        }