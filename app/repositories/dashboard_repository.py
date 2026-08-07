from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.api_key import ApiKey
from app.models.client import Client
from app.models.invoice import Invoice
from app.models.payment import Payment
from app.models.project import Project
from app.models.usage_event import UsageEvent
from app.schemas.enums import InvoiceStatus, PaymentStatus

class DashboardRepository:

    @staticmethod
    def get_dashboard_data(db: Session, user_id: int):
        now = datetime.now(timezone.utc)
        start_of_month = now.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)

        proj_stats = (
            db.query(
                func.count(func.distinct(Project.id)).label("total_projects"),
                func.count(func.distinct(Client.id)).label("total_clients"),
            )
            .outerjoin(Client, Client.project_id == Project.id)
            .filter(Project.user_id == user_id)
            .first()
        )

        active_api_keys = (
            db.query(func.count(ApiKey.id))
            .join(Client, ApiKey.client_id == Client.id)
            .join(Project, Client.project_id == Project.id)
            .filter(Project.user_id == user_id, ApiKey.revoked.is_(False))
            .scalar()
            or 0
        )

        invoice_stats = (
            db.query(
                func.count(Invoice.id)
                .filter(Invoice.status == InvoiceStatus.PENDING)
                .label("pending_invoices"),
                func.count(Invoice.id)
                .filter(Invoice.status == InvoiceStatus.PAID)
                .label("paid_invoices"),
                func.coalesce(
                    func.sum(Invoice.total_amount).filter(
                        Invoice.status == InvoiceStatus.PAID,
                        Invoice.created_at >= start_of_month,
                    ),
                    Decimal("0.00"),
                ).label("revenue_this_month"),
            )
            .join(Project, Invoice.project_id == Project.id)
            .filter(Project.user_id == user_id)
            .first()
        )

        failed_payments = (
            db.query(func.count(Payment.id))
            .join(Invoice, Payment.invoice_id == Invoice.id)
            .join(Project, Invoice.project_id == Project.id)
            .filter(
                Project.user_id == user_id,
                Payment.status == PaymentStatus.FAILED,
            )
            .scalar()
            or 0
        )

        usage_events_today = (
            db.query(func.coalesce(func.sum(UsageEvent.quantity), 0))
            .join(Project, UsageEvent.project_id == Project.id)
            .filter(
                Project.user_id == user_id,
                UsageEvent.timestamp >= start_of_today,
            )
            .scalar()
            or 0
        )

        return {
            "total_clients": proj_stats.total_clients if proj_stats else 0,
            "total_projects": proj_stats.total_projects if proj_stats else 0,
            "active_api_keys": active_api_keys,
            "pending_invoices": (
                invoice_stats.pending_invoices if invoice_stats else 0
            ),
            "paid_invoices": (
                invoice_stats.paid_invoices if invoice_stats else 0
            ),
            "revenue_this_month": (
                invoice_stats.revenue_this_month
                if invoice_stats
                else Decimal("0.00")
            ),
            "failed_payments": failed_payments,
            "usage_events_today": usage_events_today,
        }

                            