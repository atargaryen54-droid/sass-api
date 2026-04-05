from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.usage_event import UsageEvent
from app.models.pricing_rule import PricingRule
from app.core.utils import currency_round


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
