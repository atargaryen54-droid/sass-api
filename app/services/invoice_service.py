import logging
from sqlalchemy.orm import Session
from fastapi import HTTPException
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from dateutil.relativedelta import relativedelta
from sqlalchemy import func
from sqlalchemy.orm import Session, contains_eager, joinedload
from app.core.utils import currency_round
from app.models.event_type import EventType
from app.models.pricing_rule import PricingRule
from app.models.project import Project
from app.models.usage_event import UsageEvent
from app.repositories.invoice_repository import InvoiceRepository
from app.schemas.invoice import InvoiceFilter
from app.schemas.enums import BillingFrequency


class InvoiceService:
    @staticmethod
    def list_invoices(
        db: Session, 
        user_id: int,
        page: int, 
        page_size: int, 
        filters: InvoiceFilter):

        return InvoiceRepository.list_by_user(db, user_id, page, page_size, filters)
    
    
    @staticmethod
    def get_invoice_detail(db: Session, user_id: int, invoice_external_id: str):
        invoice = InvoiceRepository.get_detail(
                db,
                user_id,
                invoice_external_id,
            )

        if not invoice:
            raise HTTPException(
                status_code=404,
                detail="Invoice not found."
            )

        return invoice


    @staticmethod
    def generate_invoices(
        db: Session,
        project_id: int,
        period_start: datetime,
        period_end: datetime,
    ):
        # STEP 1: Lock raw uninvoiced events & eager load event_type to avoid N+1 queries
        locked_events = (
            db.query(UsageEvent)
            .join(UsageEvent.event_type)  # INNER JOIN avoids NULLs
            .options(
                contains_eager(UsageEvent.event_type)
            )  # Eagerly populates event.event_type
            .filter(
                UsageEvent.project_id == project_id,
                UsageEvent.timestamp >= period_start,
                UsageEvent.timestamp <= period_end,
                UsageEvent.invoice_id.is_(None),
            )
            .with_for_update()
            .all()
        )

        if not locked_events:
            return []

        # STEP 2: Load pricing rules and map by event_type_id
        pricing_rules = (
            db.query(PricingRule)
            .join(PricingRule.event_type)
            .filter(EventType.project_id == project_id)
            .all()
        )

        pricing_map = {
            rule.event_type_id: Decimal(str(rule.price_per_unit))
            for rule in pricing_rules
        }

        # STEP 3: Aggregate events in memory by client_id & event_type_id
        aggregation_map = defaultdict(
            lambda: {
                "items": defaultdict(
                    lambda: {
                        "event_code": "",
                        "quantity": 0,
                        "unit_price": Decimal("0.00"),
                        "total": Decimal("0.00"),
                        "event_ids": [],
                    }
                )
            }
        )

        warnings = []

        for event in locked_events:
            unit_price = pricing_map.get(event.event_type_id)

            if unit_price is None:
                # Safely extract event_code or fall back to ID if relationship is missing
                event_code = (
                    event.event_type.event_code
                    if (event.event_type and event.event_type.event_code)
                    else f"ID:{event.event_type_id}"
                )

                warning = (
                    f"No pricing rule found for event_code='{event_code}' "
                    f"(event_type_id={event.event_type_id}) in project_id={project_id}"
                )

                warnings.append(warning)
                logging.warning(warning)
                unit_price = Decimal("0.00")

            line_total = Decimal(str(event.quantity)) * unit_price
            client_bucket = aggregation_map[event.client_id]

            # Group by event_type_id
            item = client_bucket["items"][event.event_type_id]

            # Store string code for the final invoice payload
            item["event_code"] = (
                event.event_type.event_code
                if event.event_type
                else str(event.event_type_id)
            )
            item["quantity"] += event.quantity
            item["unit_price"] = unit_price
            item["total"] += line_total
            item["event_ids"].append(event.id)

        # STEP 4: Create invoices
        created_invoices = []

        for client_id, data in aggregation_map.items():
            items = []
            all_event_ids = []
            total_amount = Decimal("0.00")

            for event_type_id, item_data in data["items"].items():
                item_total = item_data["total"]
                total_amount += item_total

                items.append({
                    "event_type_id": event_type_id,
                    "event_code": item_data[
                        "event_code"
                    ],  # String code for UI/Invoices
                    "quantity": item_data["quantity"],
                    "unit_price": float(item_data["unit_price"]),
                    "total": float(item_total),
                })

                all_event_ids.extend(item_data["event_ids"])

            invoice = InvoiceRepository.create_invoice(
                db=db,
                project_id=project_id,
                client_id=client_id,
                total_amount=float(total_amount),
                period_start=period_start,
                period_end=period_end,
                items=items,
            )

            # STEP 5: Mark ONLY the exact locked events as invoiced
            db.query(UsageEvent).filter(
                UsageEvent.id.in_(all_event_ids)
            ).update(
                {"invoice_id": invoice.id},
                synchronize_session=False,
            )

            created_invoices.append({
                "invoice_id": invoice.id,
                "client_id": invoice.client_id,
                "total_amount": float(total_amount),
                "period_start": str(invoice.period_start),
                "period_end": str(invoice.period_end),
                "items": items,
            })

        return created_invoices
    
    @staticmethod
    def generate_project_billing(db: Session, project: Project):
        try:
            # 1. Calculate periods
            if project.billing_frequency == BillingFrequency.MONTHLY:
                period_start = project.next_billing_date - relativedelta(months=1)
                period_end = project.next_billing_date
                next_date = project.next_billing_date + relativedelta(months=1)

            elif project.billing_frequency == BillingFrequency.WEEKLY:
                period_start = project.next_billing_date - relativedelta(weeks=1)
                period_end = project.next_billing_date
                next_date = project.next_billing_date + relativedelta(weeks=1)

            elif project.billing_frequency == BillingFrequency.DAILY:
                period_start = project.next_billing_date - relativedelta(days=1)
                period_end = project.next_billing_date
                next_date = project.next_billing_date + relativedelta(days=1)

            else:
                raise ValueError(
                    f"Unsupported billing frequency: {project.billing_frequency}"
                )

            # 2. Stage invoice creation
            InvoiceService.generate_invoices(
                db=db,
                project_id=project.id,
                period_start=period_start,
                period_end=period_end,
            )
            logging.info(
                f"Advancing project_id={project.id} next_billing_date "
                f"from {project.next_billing_date} to {next_date}"
            )

            # 3. Stage date advancement
            project.next_billing_date = next_date

            # 4. Commit everything atomically
            db.commit()
            logging.info(f"Successfully committed billing for project_id={project.id}")

        except Exception:
            db.rollback()
            raise 












































    