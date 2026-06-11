from sqlalchemy.orm import Session
from sqlalchemy import func
# from uvicorn import logging

from app.models.usage_event import UsageEvent
from app.models.pricing_rule import PricingRule
from app.core.utils import currency_round
from collections import defaultdict
from datetime import datetime
from app.repositories.invoice_repository import InvoiceRepository
import logging
from decimal import Decimal

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
    def generate_invoices(
        db: Session,
        project_id: int,
        period_start,
        period_end
    ):

        try:

            # STEP 1:
            # Lock raw uninvoiced events
            # This prevents concurrent billing jobs
            # from selecting the same events

            locked_events = (
                db.query(UsageEvent)
                .filter(
                    UsageEvent.project_id == project_id,
                    UsageEvent.timestamp >= period_start,
                    UsageEvent.timestamp <= period_end,
                    UsageEvent.invoice_id == None
                )
                .with_for_update()
                .all()
            )

            if not locked_events:
                return []

            # STEP 2:
            # Load pricing rules for the project

            pricing_rules = (
                db.query(PricingRule)
                .filter(PricingRule.project_id == project_id)
                .all()
            )

            pricing_map = {
                rule.event_type: Decimal(str(rule.price_per_unit))
                for rule in pricing_rules
            }

            # STEP 3:
            # Aggregate events in memory

            aggregation_map = defaultdict(lambda: {
                "items": defaultdict(lambda: {
                    "quantity": 0,
                    "unit_price": Decimal("0.00"),
                    "total": Decimal("0.00"),
                    "event_ids": []
                })
            })

            warnings = []

            for event in locked_events:

                unit_price = pricing_map.get(event.event_type)

                if unit_price is None:

                    warning = (
                        f"No pricing rule for "
                        f"event_type='{event.event_type}' "
                        f"in project_id={project_id}"
                    )

                    warnings.append(warning)
                    logging.warning(warning)

                    unit_price = Decimal("0.00")

                line_total = Decimal(str(event.quantity)) * unit_price

                client_bucket = aggregation_map[event.client_id]

                item = client_bucket["items"][event.event_type]

                item["quantity"] += event.quantity
                item["unit_price"] = unit_price
                item["total"] += line_total
                item["event_ids"].append(event.id)

            # STEP 4:
            # Create invoices

            created_invoices = []

            for client_id, data in aggregation_map.items():

                items = []
                all_event_ids = []

                total_amount = Decimal("0.00")

                for event_type, item_data in data["items"].items():

                    item_total = item_data["total"]

                    total_amount += item_total

                    items.append({
                        "event_type": event_type,
                        "quantity": item_data["quantity"],
                        "unit_price": float(item_data["unit_price"]),
                        "total": float(item_total)
                    })

                    all_event_ids.extend(item_data["event_ids"])

                invoice = InvoiceRepository.create_invoice(
                    db=db,
                    project_id=project_id,
                    client_id=client_id,
                    total_amount=float(total_amount),
                    period_start=period_start,
                    period_end=period_end,
                    items=items
                )

                # STEP 5:
                # Mark ONLY the exact locked events
                # as invoiced

                (
                    db.query(UsageEvent)
                    .filter(UsageEvent.id.in_(all_event_ids))
                    .update(
                        {"invoice_id": invoice.id},
                        synchronize_session=False
                    )
                )

                created_invoices.append({
                    "invoice_id": invoice.id,
                    "client_id": invoice.client_id,
                    "total_amount": float(total_amount),
                    "period_start": str(invoice.period_start),
                    "period_end": str(invoice.period_end),
                    "items": items
                })

            # STEP 6:
            # Commit EVERYTHING atomically

            db.commit()

            return created_invoices

        except Exception:

            db.rollback()

            raise



