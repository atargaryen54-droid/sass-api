"""
Tests for ReconciliationService.reconcile_payments and .reconcile_refunds.

The single most important property here is the try/except/continue inside
each loop: one payment or refund throwing while talking to the provider
must not stop the rest of the batch from being reconciled. Everything else
(scoping, status sync, failure_reason capture, the refund -> payment ->
invoice cascade) is tested too, but the batch-resilience tests are the
ones that would be easy to silently break by "cleaning up" the try/except
later, so they get the most scrutiny.

Called directly against the real test DB. The provider is always mocked
via PaymentProviderFactory.get so nothing here touches the network.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import pytest

from app.models.user import User
from app.models.project import Project
from app.models.client import Client
from app.models.invoice import Invoice
from app.models.payment import Payment
from app.models.refund import Refund
from app.schemas.enums import (
    BillingFrequency,
    PaymentProvider,
    InvoiceStatus,
    PaymentStatus,
    RefundStatus,
)
from app.services.reconcilliation_service import ReconciliationService


# ---------------------------------------------------------------------------
# ORM fixtures
# ---------------------------------------------------------------------------

def make_user(db):
    user = User(
        email=f"{uuid.uuid4().hex}@example.com",
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


def make_project(db):
    user = make_user(db)
    project = Project(
        user_id=user.id,
        name=f"project-{uuid.uuid4().hex[:8]}",
        payment_provider=PaymentProvider.STRIPE,
        billing_frequency=BillingFrequency.MONTHLY,
        next_billing_date=datetime.now(timezone.utc),
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def make_client(db, project):
    client = Client(
        project_id=project.id,
        name=f"client-{uuid.uuid4().hex[:8]}",
        email=f"{uuid.uuid4().hex}@example.com",
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


def make_invoice(db, status=InvoiceStatus.PENDING, total_amount=100.0):
    project = make_project(db)
    client = make_client(db, project)
    invoice = Invoice(
        project_id=project.id,
        client_id=client.id,
        total_amount=total_amount,
        status=status.value,
        period_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        period_end=datetime(2026, 1, 31, tzinfo=timezone.utc),
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice


def make_payment(
    db, status=PaymentStatus.INITIATED, amount=100.0, invoice=None, provider_payment_id=None
):
    invoice = invoice or make_invoice(db, total_amount=amount)
    payment = Payment(
        invoice_id=invoice.id,
        provider=PaymentProvider.STRIPE,
        provider_payment_id=provider_payment_id or f"pi_{uuid.uuid4().hex[:12]}",
        amount=amount,
        currency="USD",
        status=status.value,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


def make_refund(db, payment, amount, status=RefundStatus.PENDING, provider_refund_id=None):
    refund = Refund(
        payment_id=payment.id,
        provider=PaymentProvider.STRIPE,
        provider_refund_id=provider_refund_id or f"re_{uuid.uuid4().hex[:12]}",
        amount=amount,
        currency="USD",
        status=status.value,
    )
    db.add(refund)
    db.commit()
    db.refresh(refund)
    return refund


def provider_returning(status_by_provider_id, key="status", reason_by_provider_id=None):
    """
    Builds a fake provider whose get_payment_status/get_refund_status reply
    differently depending on which provider id it's asked about -- needed
    because a single reconcile_* call processes several rows in one loop,
    each against "the provider", and we need to control each independently
    (including making one of them raise).
    """
    reason_by_provider_id = reason_by_provider_id or {}

    def _respond(provider_id):
        outcome = status_by_provider_id[provider_id]
        if isinstance(outcome, Exception):
            raise outcome
        result = {"status": outcome}
        if provider_id in reason_by_provider_id:
            result["reason"] = reason_by_provider_id[provider_id]
        return result

    fake = MagicMock()
    fake.get_payment_status.side_effect = _respond
    fake.get_refund_status.side_effect = _respond
    return fake


# ---------------------------------------------------------------------------
# reconcile_payments
# ---------------------------------------------------------------------------

class TestReconcilePayments:

    def test_only_reconciles_initiated_and_processing_payments(self, db):
        initiated = make_payment(db, status=PaymentStatus.INITIATED)
        processing = make_payment(db, status=PaymentStatus.PROCESSING)
        succeeded = make_payment(db, status=PaymentStatus.SUCCEEDED)
        created = make_payment(db, status=PaymentStatus.CREATED)

        fake_provider = provider_returning({
            initiated.provider_payment_id: PaymentStatus.SUCCEEDED.value,
            processing.provider_payment_id: PaymentStatus.SUCCEEDED.value,
            succeeded.provider_payment_id: PaymentStatus.FAILED.value,  # should never be asked
            created.provider_payment_id: PaymentStatus.FAILED.value,  # should never be asked
        })

        with patch("app.payment.provider_factory.PaymentProviderFactory.get", return_value=fake_provider):
            ReconciliationService.reconcile_payments(db)

        db.refresh(initiated)
        db.refresh(processing)
        db.refresh(succeeded)
        db.refresh(created)

        assert initiated.status == PaymentStatus.SUCCEEDED
        assert processing.status == PaymentStatus.SUCCEEDED
        assert succeeded.status == PaymentStatus.SUCCEEDED  # unchanged
        assert created.status == PaymentStatus.CREATED  # unchanged
        fake_provider.get_payment_status.assert_any_call(initiated.provider_payment_id)
        fake_provider.get_payment_status.assert_any_call(processing.provider_payment_id)
        assert fake_provider.get_payment_status.call_count == 2

    def test_status_change_from_provider_is_applied(self, db):
        payment = make_payment(db, status=PaymentStatus.PROCESSING)
        fake_provider = provider_returning({payment.provider_payment_id: PaymentStatus.SUCCEEDED.value})

        with patch("app.payment.provider_factory.PaymentProviderFactory.get", return_value=fake_provider):
            ReconciliationService.reconcile_payments(db)

        db.refresh(payment)
        assert payment.status == PaymentStatus.SUCCEEDED

    def test_failed_result_sets_failure_reason(self, db):
        payment = make_payment(db, status=PaymentStatus.PROCESSING)
        fake_provider = provider_returning(
            {payment.provider_payment_id: PaymentStatus.FAILED.value},
            reason_by_provider_id={payment.provider_payment_id: "card_declined"},
        )

        with patch("app.payment.provider_factory.PaymentProviderFactory.get", return_value=fake_provider):
            ReconciliationService.reconcile_payments(db)

        db.refresh(payment)
        assert payment.status == PaymentStatus.FAILED
        assert payment.failure_reason == "card_declined"

    def test_no_change_when_provider_status_matches_current_status(self, db):
        payment = make_payment(db, status=PaymentStatus.PROCESSING)
        fake_provider = provider_returning({payment.provider_payment_id: PaymentStatus.PROCESSING.value})

        with patch("app.payment.provider_factory.PaymentProviderFactory.get", return_value=fake_provider):
            ReconciliationService.reconcile_payments(db)

        db.refresh(payment)
        assert payment.status == PaymentStatus.PROCESSING
        assert payment.failure_reason is None

    def test_one_payment_failure_does_not_stop_the_rest_of_the_batch(self, db):
        good_1 = make_payment(db, status=PaymentStatus.INITIATED)
        broken = make_payment(db, status=PaymentStatus.INITIATED)
        good_2 = make_payment(db, status=PaymentStatus.PROCESSING)

        fake_provider = provider_returning({
            good_1.provider_payment_id: PaymentStatus.SUCCEEDED.value,
            broken.provider_payment_id: RuntimeError("provider timeout"),
            good_2.provider_payment_id: PaymentStatus.FAILED.value,
        })

        with patch("app.payment.provider_factory.PaymentProviderFactory.get", return_value=fake_provider):
            # must not raise -- one bad row can't take down the whole batch
            ReconciliationService.reconcile_payments(db)

        db.refresh(good_1)
        db.refresh(broken)
        db.refresh(good_2)

        assert good_1.status == PaymentStatus.SUCCEEDED
        assert good_2.status == PaymentStatus.FAILED
        # the broken one is untouched, not half-updated or crashed into a bad state
        assert broken.status == PaymentStatus.INITIATED

    def test_no_reconcilable_payments_is_a_no_op(self, db):
        with patch("app.payment.provider_factory.PaymentProviderFactory.get") as mock_get:
            ReconciliationService.reconcile_payments(db)
        mock_get.assert_not_called()


# ---------------------------------------------------------------------------
# reconcile_refunds
# ---------------------------------------------------------------------------

class TestReconcileRefunds:

    def test_only_reconciles_pending_refunds(self, db):
        payment = make_payment(db, status=PaymentStatus.SUCCEEDED, amount=100.0)
        pending = make_refund(db, payment, amount=30.0, status=RefundStatus.PENDING)
        succeeded = make_refund(db, payment, amount=10.0, status=RefundStatus.SUCCEEDED)
        created = make_refund(db, payment, amount=5.0, status=RefundStatus.CREATED)

        fake_provider = provider_returning({
            pending.provider_refund_id: RefundStatus.FAILED.value,
            succeeded.provider_refund_id: RefundStatus.FAILED.value,  # should never be asked
            created.provider_refund_id: RefundStatus.FAILED.value,  # should never be asked
        })

        with patch("app.payment.provider_factory.PaymentProviderFactory.get", return_value=fake_provider):
            ReconciliationService.reconcile_refunds(db)

        db.refresh(pending)
        db.refresh(succeeded)
        db.refresh(created)

        assert pending.status == RefundStatus.FAILED
        assert succeeded.status == RefundStatus.SUCCEEDED  # unchanged
        assert created.status == RefundStatus.CREATED  # unchanged
        assert fake_provider.get_refund_status.call_count == 1

    def test_failed_result_sets_failure_reason_and_does_not_touch_payment(self, db):
        payment = make_payment(db, status=PaymentStatus.SUCCEEDED, amount=100.0)
        refund = make_refund(db, payment, amount=100.0, status=RefundStatus.PENDING)

        fake_provider = provider_returning(
            {refund.provider_refund_id: RefundStatus.FAILED.value},
            reason_by_provider_id={refund.provider_refund_id: "insufficient provider funds"},
        )

        with patch("app.payment.provider_factory.PaymentProviderFactory.get", return_value=fake_provider):
            ReconciliationService.reconcile_refunds(db)

        db.refresh(refund)
        db.refresh(payment)
        assert refund.status == RefundStatus.FAILED
        assert refund.failure_reason == "insufficient provider funds"
        assert payment.status == PaymentStatus.SUCCEEDED  # untouched

    def test_succeeded_refund_cascades_to_payment_and_invoice_when_fully_refunded(self, db):
        invoice = make_invoice(db, status=InvoiceStatus.PAID, total_amount=100.0)
        payment = make_payment(db, status=PaymentStatus.SUCCEEDED, amount=100.0, invoice=invoice)
        refund = make_refund(db, payment, amount=100.0, status=RefundStatus.PENDING)

        fake_provider = provider_returning({refund.provider_refund_id: RefundStatus.SUCCEEDED.value})

        with patch("app.payment.provider_factory.PaymentProviderFactory.get", return_value=fake_provider):
            ReconciliationService.reconcile_refunds(db)

        db.refresh(refund)
        db.refresh(payment)
        db.refresh(invoice)
        assert refund.status == RefundStatus.SUCCEEDED
        assert payment.status == PaymentStatus.REFUNDED
        assert invoice.status == InvoiceStatus.REFUNDED

    def test_succeeded_partial_refund_does_not_cascade_yet(self, db):
        invoice = make_invoice(db, status=InvoiceStatus.PAID, total_amount=100.0)
        payment = make_payment(db, status=PaymentStatus.SUCCEEDED, amount=100.0, invoice=invoice)
        refund = make_refund(db, payment, amount=40.0, status=RefundStatus.PENDING)

        fake_provider = provider_returning({refund.provider_refund_id: RefundStatus.SUCCEEDED.value})

        with patch("app.payment.provider_factory.PaymentProviderFactory.get", return_value=fake_provider):
            ReconciliationService.reconcile_refunds(db)

        db.refresh(refund)
        db.refresh(payment)
        db.refresh(invoice)
        assert refund.status == RefundStatus.SUCCEEDED
        assert payment.status == PaymentStatus.SUCCEEDED  # not fully refunded yet
        assert invoice.status == InvoiceStatus.PAID

    def test_one_refund_failure_does_not_stop_the_rest_of_the_batch(self, db):
        payment = make_payment(db, status=PaymentStatus.SUCCEEDED, amount=100.0)
        good = make_refund(db, payment, amount=30.0, status=RefundStatus.PENDING)
        broken = make_refund(db, payment, amount=20.0, status=RefundStatus.PENDING)

        fake_provider = provider_returning({
            good.provider_refund_id: RefundStatus.FAILED.value,
            broken.provider_refund_id: RuntimeError("provider timeout"),
        })

        with patch("app.payment.provider_factory.PaymentProviderFactory.get", return_value=fake_provider):
            # must not raise
            ReconciliationService.reconcile_refunds(db)

        db.refresh(good)
        db.refresh(broken)
        assert good.status == RefundStatus.FAILED
        assert broken.status == RefundStatus.PENDING  # untouched, not crashed mid-update

    def test_no_reconcilable_refunds_is_a_no_op(self, db):
        with patch("app.payment.provider_factory.PaymentProviderFactory.get") as mock_get:
            ReconciliationService.reconcile_refunds(db)
        mock_get.assert_not_called()