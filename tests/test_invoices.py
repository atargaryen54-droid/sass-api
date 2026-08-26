"""
Tests for the billing engine: InvoiceService.generate_invoices (the
aggregation logic that turns raw usage events into invoices),
InvoiceService.generate_project_billing (period math + next_billing_date
rollover + atomicity), and InvoiceStatusService (the status state machine).

generate_invoices / generate_project_billing are tested by calling the
service directly against the real test DB and inserting usage events
through the ORM, rather than through the HTTP layer or the worker/Celery
task -- this is pure billing-math logic and doesn't need auth, routing, or
a task queue to exercise it. InvoiceStatusService needs no DB at all: it
only mutates a python attribute on whatever Invoice object you hand it.
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from dateutil.relativedelta import relativedelta

from app.models.user import User
from app.models.project import Project
from app.models.client import Client
from app.models.event_type import EventType
from app.models.pricing_rule import PricingRule
from app.models.api_key import ApiKey
from app.models.usage_event import UsageEvent
from app.models.invoice import Invoice
from app.schemas.enums import BillingFrequency, PaymentProvider, InvoiceStatus
from app.services.invoice_service import InvoiceService
from app.services.invoice_status_service import InvoiceStatusService
from app.repositories.invoice_repository import InvoiceRepository


# ---------------------------------------------------------------------------
# ORM fixtures -- straight to the DB, no HTTP layer needed for this file.
# ---------------------------------------------------------------------------

def make_user(db, email=None):
    user = User(
        email=email or f"{uuid.uuid4().hex}@example.com",
        password_hash="hashed",
        full_name="Test User",
        company_name="Test Co",
        timezone="UTC",
        default_currency="USD",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_project(
    db,
    user=None,
    billing_frequency=BillingFrequency.MONTHLY,
    next_billing_date=None,
):
    user = user or make_user(db)
    project = Project(
        user_id=user.id,
        name=f"project-{uuid.uuid4().hex[:8]}",
        payment_provider=PaymentProvider.STRIPE,
        billing_frequency=billing_frequency,
        next_billing_date=next_billing_date or datetime.now(timezone.utc),
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def make_client(db, project, name=None, email=None):
    name = name or f"client-{uuid.uuid4().hex[:8]}"
    client = Client(
        project_id=project.id,
        name=name,
        email=email or f"{name}@example.com",
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


def make_event_type(db, project, event_code=None):
    event_type = EventType(
        project_id=project.id,
        event_code=event_code or f"event-{uuid.uuid4().hex[:8]}",
        name="test event",
    )
    db.add(event_type)
    db.commit()
    db.refresh(event_type)
    return event_type


def make_pricing_rule(db, event_type, price=1.0):
    rule = PricingRule(event_type_id=event_type.id, price_per_unit=price)
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def make_api_key(db, client):
    key = ApiKey(
        client_id=client.id,
        name=f"key-{uuid.uuid4().hex[:8]}",
        key_prefix="sk_live_test",
        key_mask="test",
        key_hash="hashed",
    )
    db.add(key)
    db.commit()
    db.refresh(key)
    return key


def make_usage_event(
    db,
    project,
    client,
    event_type,
    api_key,
    quantity=1,
    timestamp=None,
    invoice_id=None,
):
    event = UsageEvent(
        project_id=project.id,
        client_id=client.id,
        api_key_id=api_key.id,
        event_type_id=event_type.id,
        quantity=quantity,
        idempotency_key=str(uuid.uuid4()),
        invoice_id=invoice_id,
    )
    if timestamp is not None:
        event.timestamp = timestamp
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


PERIOD_START = datetime(2026, 1, 1, tzinfo=timezone.utc)
PERIOD_END = datetime(2026, 1, 31, 23, 59, 59, tzinfo=timezone.utc)
IN_PERIOD = datetime(2026, 1, 15, tzinfo=timezone.utc)
BEFORE_PERIOD = datetime(2025, 12, 15, tzinfo=timezone.utc)
AFTER_PERIOD = datetime(2026, 2, 15, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# generate_invoices: the core aggregation logic.
# ---------------------------------------------------------------------------

class TestGenerateInvoices:

    def test_aggregates_quantity_and_total_for_one_client_one_event_type(self, db):
        project = make_project(db)
        client = make_client(db, project)
        event_type = make_event_type(db, project)
        make_pricing_rule(db, event_type, price=2.0)
        api_key = make_api_key(db, client)

        make_usage_event(db, project, client, event_type, api_key, quantity=5, timestamp=IN_PERIOD)
        make_usage_event(db, project, client, event_type, api_key, quantity=3, timestamp=IN_PERIOD)

        result = InvoiceService.generate_invoices(
            db, project_id=project.id, period_start=PERIOD_START, period_end=PERIOD_END
        )

        assert len(result) == 1
        invoice = result[0]
        assert invoice["client_id"] == client.id
        assert invoice["total_amount"] == pytest.approx(16.0)  # (5+3) * 2.0
        assert len(invoice["items"]) == 1
        assert invoice["items"][0]["quantity"] == 8
        assert invoice["items"][0]["total"] == pytest.approx(16.0)

    def test_separates_invoices_by_client(self, db):
        project = make_project(db)
        client_a = make_client(db, project, name="client-a")
        client_b = make_client(db, project, name="client-b")
        event_type = make_event_type(db, project)
        make_pricing_rule(db, event_type, price=1.0)
        key_a = make_api_key(db, client_a)
        key_b = make_api_key(db, client_b)

        make_usage_event(db, project, client_a, event_type, key_a, quantity=10, timestamp=IN_PERIOD)
        make_usage_event(db, project, client_b, event_type, key_b, quantity=4, timestamp=IN_PERIOD)

        result = InvoiceService.generate_invoices(
            db, project_id=project.id, period_start=PERIOD_START, period_end=PERIOD_END
        )

        assert len(result) == 2
        by_client = {inv["client_id"]: inv for inv in result}
        assert by_client[client_a.id]["total_amount"] == pytest.approx(10.0)
        assert by_client[client_b.id]["total_amount"] == pytest.approx(4.0)

    def test_separates_line_items_by_event_type_within_one_client(self, db):
        project = make_project(db)
        client = make_client(db, project)
        api_key = make_api_key(db, client)

        event_type_a = make_event_type(db, project, event_code="api_call")
        make_pricing_rule(db, event_type_a, price=1.0)
        event_type_b = make_event_type(db, project, event_code="storage_gb")
        make_pricing_rule(db, event_type_b, price=5.0)

        make_usage_event(db, project, client, event_type_a, api_key, quantity=100, timestamp=IN_PERIOD)
        make_usage_event(db, project, client, event_type_b, api_key, quantity=2, timestamp=IN_PERIOD)

        result = InvoiceService.generate_invoices(
            db, project_id=project.id, period_start=PERIOD_START, period_end=PERIOD_END
        )

        assert len(result) == 1
        invoice = result[0]
        assert invoice["total_amount"] == pytest.approx(100 * 1.0 + 2 * 5.0)
        assert len(invoice["items"]) == 2
        codes = {item["event_code"] for item in invoice["items"]}
        assert codes == {"api_call", "storage_gb"}

    def test_excludes_already_invoiced_events(self, db):
        project = make_project(db)
        client = make_client(db, project)
        event_type = make_event_type(db, project)
        make_pricing_rule(db, event_type, price=1.0)
        api_key = make_api_key(db, client)

        # a real prior invoice to point the "already billed" event at --
        # invoice_id is a genuine FK, so this can't be a placeholder int
        prior_invoice = InvoiceRepository.create_invoice(
            db,
            project_id=project.id,
            client_id=client.id,
            total_amount=999.0,
            period_start=BEFORE_PERIOD,
            period_end=BEFORE_PERIOD,
            items=[],
        )
        db.commit()

        make_usage_event(
            db, project, client, event_type, api_key,
            quantity=999, timestamp=IN_PERIOD, invoice_id=prior_invoice.id,
        )
        make_usage_event(db, project, client, event_type, api_key, quantity=7, timestamp=IN_PERIOD)

        result = InvoiceService.generate_invoices(
            db, project_id=project.id, period_start=PERIOD_START, period_end=PERIOD_END
        )

        assert len(result) == 1
        assert result[0]["total_amount"] == pytest.approx(7.0)

    def test_excludes_events_outside_period(self, db):
        project = make_project(db)
        client = make_client(db, project)
        event_type = make_event_type(db, project)
        make_pricing_rule(db, event_type, price=1.0)
        api_key = make_api_key(db, client)

        make_usage_event(db, project, client, event_type, api_key, quantity=50, timestamp=BEFORE_PERIOD)
        make_usage_event(db, project, client, event_type, api_key, quantity=60, timestamp=AFTER_PERIOD)
        make_usage_event(db, project, client, event_type, api_key, quantity=3, timestamp=IN_PERIOD)

        result = InvoiceService.generate_invoices(
            db, project_id=project.id, period_start=PERIOD_START, period_end=PERIOD_END
        )

        assert len(result) == 1
        assert result[0]["items"][0]["quantity"] == 3

    def test_missing_pricing_rule_falls_back_to_zero_and_does_not_crash(self, db):
        project = make_project(db)
        client = make_client(db, project)
        event_type = make_event_type(db, project)
        # deliberately no pricing rule created
        api_key = make_api_key(db, client)

        make_usage_event(db, project, client, event_type, api_key, quantity=20, timestamp=IN_PERIOD)

        result = InvoiceService.generate_invoices(
            db, project_id=project.id, period_start=PERIOD_START, period_end=PERIOD_END
        )

        assert len(result) == 1
        assert result[0]["items"][0]["unit_price"] == 0.0
        assert result[0]["total_amount"] == 0.0

    def test_no_uninvoiced_events_returns_empty_list(self, db):
        project = make_project(db)

        result = InvoiceService.generate_invoices(
            db, project_id=project.id, period_start=PERIOD_START, period_end=PERIOD_END
        )

        assert result == []

    def test_events_are_marked_invoiced_and_not_billed_again(self, db):
        project = make_project(db)
        client = make_client(db, project)
        event_type = make_event_type(db, project)
        make_pricing_rule(db, event_type, price=1.0)
        api_key = make_api_key(db, client)

        event = make_usage_event(db, project, client, event_type, api_key, quantity=1, timestamp=IN_PERIOD)

        first_run = InvoiceService.generate_invoices(
            db, project_id=project.id, period_start=PERIOD_START, period_end=PERIOD_END
        )
        assert len(first_run) == 1

        db.refresh(event)
        assert event.invoice_id == first_run[0]["invoice_id"]

        second_run = InvoiceService.generate_invoices(
            db, project_id=project.id, period_start=PERIOD_START, period_end=PERIOD_END
        )
        assert second_run == []

    def test_a_client_with_no_events_does_not_get_an_invoice(self, db):
        project = make_project(db)
        client_a = make_client(db, project, name="has-events")
        make_client(db, project, name="no-events")
        event_type = make_event_type(db, project)
        make_pricing_rule(db, event_type, price=1.0)
        key_a = make_api_key(db, client_a)

        make_usage_event(db, project, client_a, event_type, key_a, quantity=1, timestamp=IN_PERIOD)

        result = InvoiceService.generate_invoices(
            db, project_id=project.id, period_start=PERIOD_START, period_end=PERIOD_END
        )

        assert len(result) == 1
        assert result[0]["client_id"] == client_a.id


# ---------------------------------------------------------------------------
# generate_project_billing: period math, next_billing_date rollover, and
# atomicity between invoice creation and the date advance.
# ---------------------------------------------------------------------------

class TestGenerateProjectBilling:

    @pytest.mark.parametrize(
        "frequency,delta_kwargs",
        [
            (BillingFrequency.DAILY, {"days": 1}),
            (BillingFrequency.WEEKLY, {"weeks": 1}),
            (BillingFrequency.MONTHLY, {"months": 1}),
        ],
    )
    def test_period_and_rollover_math(self, db, frequency, delta_kwargs):
        now = datetime.now(timezone.utc)
        anchor = now.replace(minute=0, second=0, microsecond=0) 
        project = make_project(db, billing_frequency=frequency, next_billing_date=anchor)
        client = make_client(db, project)
        event_type = make_event_type(db, project)
        make_pricing_rule(db, event_type, price=1.0)
        api_key = make_api_key(db, client)

        # one event squarely inside the expected period -- clear of the
        # boundaries so this doesn't depend on inclusive/exclusive edges.
        # (relativedelta division truncates integer fields to 0, e.g.
        # relativedelta(months=1)/2 == 0 months -- so plain timedeltas here,
        # not a fraction of the delta itself.)
        mid_period_offset = {
            BillingFrequency.DAILY: timedelta(hours=12),
            BillingFrequency.WEEKLY: timedelta(days=3),
            BillingFrequency.MONTHLY: timedelta(days=15),
        }[frequency]
        mid_period = anchor - mid_period_offset
        make_usage_event(db, project, client, event_type, api_key, quantity=1, timestamp=mid_period)

        InvoiceService.generate_project_billing(db, project)

        db.refresh(project)
        expected_next = anchor + relativedelta(**delta_kwargs)
        assert project.next_billing_date == expected_next

        invoices = db.query(Invoice).filter(Invoice.project_id == project.id).all()
        assert len(invoices) == 1
        assert invoices[0].period_start == anchor - relativedelta(**delta_kwargs)
        assert invoices[0].period_end == anchor

    def test_next_billing_date_does_not_advance_if_invoice_creation_fails(self, db):
        original_next_billing_date = datetime(2026, 4, 1, tzinfo=timezone.utc)
        project = make_project(
            db, billing_frequency=BillingFrequency.MONTHLY, next_billing_date=original_next_billing_date
        )
        client = make_client(db, project)
        event_type = make_event_type(db, project)
        make_pricing_rule(db, event_type, price=1.0)
        api_key = make_api_key(db, client)
        make_usage_event(
            db, project, client, event_type, api_key, quantity=1,
            timestamp=original_next_billing_date - timedelta(days=10),
        )

        with patch.object(
            InvoiceRepository, "create_invoice", side_effect=RuntimeError("db exploded")
        ):
            with pytest.raises(RuntimeError):
                InvoiceService.generate_project_billing(db, project)

        db.refresh(project)
        assert project.next_billing_date == original_next_billing_date

        invoices = db.query(Invoice).filter(Invoice.project_id == project.id).all()
        assert invoices == []

    def test_unsupported_billing_frequency_raises_and_rolls_back(self, db):
        original_next_billing_date = datetime(2026, 4, 1, tzinfo=timezone.utc)
        project = make_project(
            db, billing_frequency=BillingFrequency.MONTHLY, next_billing_date=original_next_billing_date
        )
        # bypass the enum to simulate bad/legacy data
        project.billing_frequency = "yearly"
        db.commit()

        with pytest.raises(ValueError):
            InvoiceService.generate_project_billing(db, project)

        db.refresh(project)
        assert project.next_billing_date == original_next_billing_date


# ---------------------------------------------------------------------------
# InvoiceStatusService: pure state machine, no DB needed.
# ---------------------------------------------------------------------------

def make_invoice(status: InvoiceStatus):
    return Invoice(status=status.value)


class TestInvoiceStatusTransitions:

    @pytest.mark.parametrize(
        "from_status,to_status",
        [
            (InvoiceStatus.GENERATED, InvoiceStatus.PENDING),
            (InvoiceStatus.GENERATED, InvoiceStatus.VOIDED),
            (InvoiceStatus.PENDING, InvoiceStatus.PAID),
            (InvoiceStatus.PENDING, InvoiceStatus.VOIDED),
            (InvoiceStatus.PAID, InvoiceStatus.REFUNDED),
        ],
    )
    def test_allowed_transitions_succeed(self, from_status, to_status):
        invoice = make_invoice(from_status)
        result = InvoiceStatusService.transition_status(invoice, to_status)
        assert result is True
        assert invoice.status == to_status

    @pytest.mark.parametrize(
        "from_status,to_status",
        [
            (InvoiceStatus.GENERATED, InvoiceStatus.PAID),
            (InvoiceStatus.GENERATED, InvoiceStatus.REFUNDED),
            (InvoiceStatus.PENDING, InvoiceStatus.GENERATED),
            (InvoiceStatus.PENDING, InvoiceStatus.REFUNDED),
            (InvoiceStatus.PAID, InvoiceStatus.VOIDED),
            (InvoiceStatus.PAID, InvoiceStatus.PENDING),
            (InvoiceStatus.VOIDED, InvoiceStatus.PENDING),
            (InvoiceStatus.VOIDED, InvoiceStatus.PAID),
            (InvoiceStatus.REFUNDED, InvoiceStatus.PENDING),
            (InvoiceStatus.REFUNDED, InvoiceStatus.PAID),
        ],
    )
    def test_disallowed_transitions_raise_and_do_not_mutate(self, from_status, to_status):
        invoice = make_invoice(from_status)
        with pytest.raises(ValueError):
            InvoiceStatusService.transition_status(invoice, to_status)
        assert invoice.status == from_status

    @pytest.mark.parametrize(
        "status",
        [
            InvoiceStatus.GENERATED,
            InvoiceStatus.PENDING,
            InvoiceStatus.PAID,
            InvoiceStatus.VOIDED,
            InvoiceStatus.REFUNDED,
        ],
    )
    def test_same_status_transition_is_a_no_op(self, status):
        invoice = make_invoice(status)
        result = InvoiceStatusService.transition_status(invoice, status)
        assert result is False
        assert invoice.status == status