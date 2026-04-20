from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.usage_event import UsageEvent
from app.models.pricing_rule import PricingRule
from app.core.utils import currency_round
from collections import defaultdict
from datetime import datetime
from app.repositories.invoice_repository import InvoiceRepository


class BillingService:
    @staticmethod
    def calculate_usage(db: Session, project_id: int):
        results = (
            db.query(
                UsageEvent.client_id,
                UsageEvent.event_type,
                func.sum(UsageEvent.quantity).label("total_quantity"),
                PricingRule.price_per_unit
            )
            .outerjoin(
                PricingRule,
                (UsageEvent.event_type == PricingRule.event_type) &
                (UsageEvent.project_id == PricingRule.project_id)
            )
            .filter(UsageEvent.project_id == project_id)
            .group_by(
                UsageEvent.client_id,
                UsageEvent.event_type,
                PricingRule.price_per_unit
            )
            .all()
        )

        output = []
        for row in results:
            unit_price = row.price_per_unit if row.price_per_unit is not None else 0.0
            total_cost = currency_round(row.total_quantity * unit_price)

            output.append({
                "client_id": row.client_id,
                "event_type": row.event_type,
                "quantity": row.total_quantity,
                "unit_price": unit_price,
                "total": float(total_cost),
                "warning": "No pricing rule found" if row.price_per_unit is None else None
            })

        return output
    
    @staticmethod
    def generate_invoices(db, project_id, period_start, period_end):

        results = (
            db.query(
                UsageEvent.client_id,
                UsageEvent.event_type,
                func.sum(UsageEvent.quantity).label("total_quantity"),
                PricingRule.price_per_unit
            )
            .join(
                PricingRule,
                (UsageEvent.event_type == PricingRule.event_type) &
                (UsageEvent.project_id == PricingRule.project_id)
            )
            .filter(
                UsageEvent.project_id == project_id,
                UsageEvent.timestamp >= period_start,
                UsageEvent.timestamp <= period_end
            )
            .group_by(
                UsageEvent.client_id,
                UsageEvent.event_type,
                PricingRule.price_per_unit
            )
            .all()
        )

        invoices_map = defaultdict(list)

        for row in results:
            unit_price = row.price_per_unit if row.price_per_unit is not None else 0.0
            total = currency_round(row.total_quantity * unit_price)

            invoices_map[row.client_id].append({
                "event_type": row.event_type,
                "quantity": row.total_quantity,
                "unit_price": row.price_per_unit,
                "total": float(total)
            }) 

        created_invoices = []

        for client_id, items in invoices_map.items():

            total_amount = sum(item["total"] for item in items)

            invoice = InvoiceRepository.create_invoice(
                db=db,
                project_id=project_id,
                client_id=client_id,
                total_amount=total_amount,
                period_start=period_start,
                period_end=period_end,
                items=items
            )

            created_invoices.append(invoice)

        return created_invoices



