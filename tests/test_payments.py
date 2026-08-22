"""
Tests for the payment lifecycle: PaymentStatusService (the status state
machine), PaymentService.create_payment (invoice guards + provider failure
handling + success path), PaymentService.retry_payment (the single-guard
condition gating retries), and PaymentService.mark_refunded_if_fully_refunded
(the refund-sum threshold that cascades a payment -> invoice to REFUNDED).

create_payment / retry_payment / mark_refunded_if_fully_refunded are called
directly against the real test DB rather than through HTTP -- ownership and
routing are already covered in test_ownership.py, this file is about the
payment state logic itself. The real Stripe provider is always mocked via
PaymentProviderFactory.get so nothing here touches the network.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi import HTTPException

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
from app.payment.payment_service import PaymentService
from app.payment.payment_status_service import PaymentStatusService
from app.payment.schemas import PaymentIntentResult


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


def make_invoice(db, project=None, client=None, status=InvoiceStatus.GENERATED, total_amount=100.0):
    project = project or make_project(db)
    client = client or make_client(db, project)
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


def make_payment(db, invoice, status=PaymentStatus.CREATED, amount=None):
    payment = Payment(
        invoice_id=invoice.id,
        provider=PaymentProvider.STRIPE,
        amount=amount if amount is not None else invoice.total_amount,
        currency="USD",
        status=status.value,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


def make_refund(db, payment, amount, status=RefundStatus.SUCCEEDED):
    refund = Refund(
        payment_id=payment.id,
        provider=PaymentProvider.STRIPE,
        amount=amount,
        currency="USD",
        status=status.value,
    )
    db.add(refund)
    db.commit()
    db.refresh(refund)
    return refund


FAKE_RESULT = PaymentIntentResult(
    provider_payment_id="pi_fake_123",
    client_secret="secret_fake_123",
    status="requires_payment_method",
)


# ---------------------------------------------------------------------------
# PaymentStatusService: pure state machine, no DB needed.
# ---------------------------------------------------------------------------

def build_payment(status: PaymentStatus):
    return Payment(status=status.value)


class TestPaymentStatusTransitions:

    @pytest.mark.parametrize(
        "from_status,to_status",
        [
            (PaymentStatus.CREATED, PaymentStatus.INITIATED),
            (PaymentStatus.CREATED, PaymentStatus.FAILED),
            (PaymentStatus.CREATED, PaymentStatus.CANCELLED),
            (PaymentStatus.INITIATED, PaymentStatus.PROCESSING),
            (PaymentStatus.INITIATED, PaymentStatus.CANCELLED),
            (PaymentStatus.INITIATED, PaymentStatus.SUCCEEDED),
            (PaymentStatus.INITIATED, PaymentStatus.FAILED),
            (PaymentStatus.PROCESSING, PaymentStatus.SUCCEEDED),
            (PaymentStatus.PROCESSING, PaymentStatus.FAILED),
            (PaymentStatus.PROCESSING, PaymentStatus.CANCELLED),
            (PaymentStatus.SUCCEEDED, PaymentStatus.REFUNDED),
        ],
    )
    def test_allowed_transitions_succeed(self, from_status, to_status):
        payment = build_payment(from_status)
        result = PaymentStatusService.transition_status(payment, to_status)
        assert result is True
        assert payment.status == to_status

    @pytest.mark.parametrize(
        "from_status,to_status",
        [
            (PaymentStatus.CREATED, PaymentStatus.PROCESSING),
            (PaymentStatus.CREATED, PaymentStatus.SUCCEEDED),
            (PaymentStatus.CREATED, PaymentStatus.REFUNDED),
            (PaymentStatus.INITIATED, PaymentStatus.CREATED),
            (PaymentStatus.PROCESSING, PaymentStatus.INITIATED),
            (PaymentStatus.PROCESSING, PaymentStatus.CREATED),
            (PaymentStatus.SUCCEEDED, PaymentStatus.FAILED),
            (PaymentStatus.SUCCEEDED, PaymentStatus.PROCESSING),
            (PaymentStatus.FAILED, PaymentStatus.INITIATED),
            (PaymentStatus.CANCELLED, PaymentStatus.INITIATED),
            (PaymentStatus.REFUNDED, PaymentStatus.SUCCEEDED),
        ],
    )
    def test_disallowed_transitions_raise_and_do_not_mutate(self, from_status, to_status):
        payment = build_payment(from_status)
        with pytest.raises(ValueError):
            PaymentStatusService.transition_status(payment, to_status)
        assert payment.status == from_status

    @pytest.mark.parametrize(
        "status",
        [
            PaymentStatus.CREATED,
            PaymentStatus.INITIATED,
            PaymentStatus.PROCESSING,
            PaymentStatus.SUCCEEDED,
            PaymentStatus.FAILED,
            PaymentStatus.CANCELLED,
            PaymentStatus.REFUNDED,
        ],
    )
    def test_same_status_transition_is_a_no_op(self, status):
        payment = build_payment(status)
        result = PaymentStatusService.transition_status(payment, status)
        assert result is False
        assert payment.status == status


# ---------------------------------------------------------------------------
# PaymentService.create_payment
# ---------------------------------------------------------------------------

class TestCreatePayment:

    @pytest.mark.parametrize("blocked_status", [InvoiceStatus.VOIDED, InvoiceStatus.PAID])
    def test_blocked_when_invoice_in_terminal_status(self, db, blocked_status):
        invoice = make_invoice(db, status=blocked_status)
        user_id = invoice.project.user_id

        with pytest.raises(HTTPException) as exc_info:
            PaymentService.create_payment(db, user_id=user_id, invoice_external_id=invoice.external_id)

        assert exc_info.value.status_code == 422

        payments = db.query(Payment).filter(Payment.invoice_id == invoice.id).all()
        assert payments == []

    def test_provider_failure_marks_payment_failed_and_reraises(self, db):
        invoice = make_invoice(db, status=InvoiceStatus.GENERATED)
        user_id = invoice.project.user_id

        with patch("app.payment.provider_factory.PaymentProviderFactory.get") as mock_get:
            mock_get.return_value.create_payment_intent.side_effect = RuntimeError("stripe down")

            with pytest.raises(RuntimeError):
                PaymentService.create_payment(db, user_id=user_id, invoice_external_id=invoice.external_id)

        payments = db.query(Payment).filter(Payment.invoice_id == invoice.id).all()
        assert len(payments) == 1
        assert payments[0].status == PaymentStatus.FAILED
        assert payments[0].failure_reason == "stripe down"

        db.refresh(invoice)
        assert invoice.status == InvoiceStatus.GENERATED

    def test_successful_payment_sets_status_and_advances_invoice(self, db):
        invoice = make_invoice(db, status=InvoiceStatus.GENERATED)
        user_id = invoice.project.user_id

        with patch("app.payment.provider_factory.PaymentProviderFactory.get") as mock_get:
            mock_get.return_value.create_payment_intent.return_value = FAKE_RESULT

            result = PaymentService.create_payment(
                db, user_id=user_id, invoice_external_id=invoice.external_id
            )

        assert result["client_secret"] == "secret_fake_123"

        payment = db.query(Payment).filter(Payment.invoice_id == invoice.id).first()
        assert payment.external_id == result["payment_external_id"]
        assert payment.status == PaymentStatus.INITIATED
        assert payment.provider_payment_id == "pi_fake_123"

        db.refresh(invoice)
        assert invoice.status == InvoiceStatus.PENDING

    def test_successful_payment_does_not_re_transition_an_already_pending_invoice(self, db):
        # simulates a retry: invoice is already PENDING from a prior attempt
        invoice = make_invoice(db, status=InvoiceStatus.PENDING)
        user_id = invoice.project.user_id

        with patch("app.payment.provider_factory.PaymentProviderFactory.get") as mock_get:
            mock_get.return_value.create_payment_intent.return_value = FAKE_RESULT

            PaymentService.create_payment(db, user_id=user_id, invoice_external_id=invoice.external_id)

        db.refresh(invoice)
        assert invoice.status == InvoiceStatus.PENDING

    def test_raises_404_for_unknown_invoice(self, db):
        project = make_project(db)
        with pytest.raises(HTTPException) as exc_info:
            PaymentService.create_payment(
                db, user_id=project.user_id, invoice_external_id="does-not-exist"
            )
        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# PaymentService.retry_payment
# ---------------------------------------------------------------------------

class TestRetryPayment:

    def test_succeeds_when_invoice_pending_and_last_payment_failed(self, db):
        invoice = make_invoice(db, status=InvoiceStatus.PENDING)
        make_payment(db, invoice, status=PaymentStatus.FAILED)
        user_id = invoice.project.user_id

        with patch("app.payment.provider_factory.PaymentProviderFactory.get") as mock_get:
            mock_get.return_value.create_payment_intent.return_value = FAKE_RESULT

            result = PaymentService.retry_payment(
                db, user_id=user_id, invoice_external_id=invoice.external_id
            )

        assert result["client_secret"] == "secret_fake_123"

        payments = db.query(Payment).filter(Payment.invoice_id == invoice.id).all()
        assert len(payments) == 2  # the original FAILED one, plus the new attempt

    def test_rejected_when_invoice_not_pending(self, db):
        invoice = make_invoice(db, status=InvoiceStatus.GENERATED)
        make_payment(db, invoice, status=PaymentStatus.FAILED)
        user_id = invoice.project.user_id

        with pytest.raises(HTTPException) as exc_info:
            PaymentService.retry_payment(db, user_id=user_id, invoice_external_id=invoice.external_id)
        assert exc_info.value.status_code == 409

    def test_rejected_when_last_payment_not_failed(self, db):
        invoice = make_invoice(db, status=InvoiceStatus.PENDING)
        make_payment(db, invoice, status=PaymentStatus.SUCCEEDED)
        user_id = invoice.project.user_id

        with pytest.raises(HTTPException) as exc_info:
            PaymentService.retry_payment(db, user_id=user_id, invoice_external_id=invoice.external_id)
        assert exc_info.value.status_code == 409

    def test_rejected_when_no_payment_attempts_exist_yet(self, db):
        invoice = make_invoice(db, status=InvoiceStatus.PENDING)
        user_id = invoice.project.user_id

        with pytest.raises(HTTPException) as exc_info:
            PaymentService.retry_payment(db, user_id=user_id, invoice_external_id=invoice.external_id)
        assert exc_info.value.status_code == 409

    def test_rejected_when_last_payment_cancelled(self, db):
        invoice = make_invoice(db, status=InvoiceStatus.PENDING)
        make_payment(db, invoice, status=PaymentStatus.CANCELLED)
        user_id = invoice.project.user_id

        with pytest.raises(HTTPException) as exc_info:
            PaymentService.retry_payment(db, user_id=user_id, invoice_external_id=invoice.external_id)
        assert exc_info.value.status_code == 409


# ---------------------------------------------------------------------------
# PaymentService.mark_refunded_if_fully_refunded
# ---------------------------------------------------------------------------
import logging
class TestMarkRefundedIfFullyRefunded:
   

    def test_partial_refund_does_not_change_payment_or_invoice_status(self, db):
        invoice = make_invoice(db, status=InvoiceStatus.PAID, total_amount=100.0)
        payment = make_payment(db, invoice, status=PaymentStatus.SUCCEEDED, amount=100.0)
        make_refund(db, payment, amount=40.0, status=RefundStatus.SUCCEEDED)

        PaymentService.mark_refunded_if_fully_refunded(db, payment.id)
        db.commit()  # mark_refunded_if_fully_refunded relies on the caller to commit,
        # same as its real caller (reconcile_refunds) does.

        db.refresh(payment)
        db.refresh(invoice)
        assert payment.status == PaymentStatus.SUCCEEDED
        assert invoice.status == InvoiceStatus.PAID

    def test_full_refund_marks_payment_and_invoice_refunded(self, db):
        invoice = make_invoice(db, status=InvoiceStatus.PAID, total_amount=100.0)
        payment = make_payment(db, invoice, status=PaymentStatus.SUCCEEDED, amount=100.0)
        make_refund(db, payment, amount=100.0, status=RefundStatus.SUCCEEDED)

        PaymentService.mark_refunded_if_fully_refunded(db, payment.id)
        db.commit()  # mark_refunded_if_fully_refunded relies on the caller to commit,
        # same as its real caller (reconcile_refunds) does.

        db.refresh(payment)
        db.refresh(invoice)
        assert payment.status == PaymentStatus.REFUNDED
        assert invoice.status == InvoiceStatus.REFUNDED

    def test_refund_total_exceeding_amount_still_marks_refunded(self, db, caplog):
        """
        Refunds that exceed the total payment amount are still full refunds 
        but for some reason the amount refunded is more than the actual
        payment amount, so status changes happen but a warning is logged about 
        this specific issue

        """
        invoice = make_invoice(db, status=InvoiceStatus.PAID, total_amount=100.0)
        payment = make_payment(db, invoice, status=PaymentStatus.SUCCEEDED, amount=100.0)
        make_refund(db, payment, amount=150.0, status=RefundStatus.SUCCEEDED)

        # 1. Capture logs at WARNING level or above
        with caplog.at_level(logging.WARNING):
            PaymentService.mark_refunded_if_fully_refunded(db, payment.id)
            db.commit()

        db.refresh(payment)
        assert payment.status == PaymentStatus.REFUNDED

        # 2. Verify the warning was emitted
        # Match the substring or pattern expected in your logger
        assert any(
            "exceeds payment amount" in record.message.lower() 
            for record in caplog.records 
            if record.levelname == "WARNING"
        )

    def test_only_succeeded_refunds_count_toward_the_total(self, db):
        invoice = make_invoice(db, status=InvoiceStatus.PAID, total_amount=100.0)
        payment = make_payment(db, invoice, status=PaymentStatus.SUCCEEDED, amount=100.0)
        make_refund(db, payment, amount=100.0, status=RefundStatus.PENDING)
        make_refund(db, payment, amount=100.0, status=RefundStatus.FAILED)

        PaymentService.mark_refunded_if_fully_refunded(db, payment.id)
        db.commit()  # mark_refunded_if_fully_refunded relies on the caller to commit,
        # same as its real caller (reconcile_refunds) does.

        db.refresh(payment)
        db.refresh(invoice)
        assert payment.status == PaymentStatus.SUCCEEDED
        assert invoice.status == InvoiceStatus.PAID

    def test_multiple_partial_succeeded_refunds_sum_to_a_full_refund(self, db):
        invoice = make_invoice(db, status=InvoiceStatus.PAID, total_amount=100.0)
        payment = make_payment(db, invoice, status=PaymentStatus.SUCCEEDED, amount=100.0)
        make_refund(db, payment, amount=50.0, status=RefundStatus.SUCCEEDED)
        make_refund(db, payment, amount=50.0, status=RefundStatus.SUCCEEDED)

        PaymentService.mark_refunded_if_fully_refunded(db, payment.id)
        db.commit()  # mark_refunded_if_fully_refunded relies on the caller to commit,
        # same as its real caller (reconcile_refunds) does.

        db.refresh(payment)
        db.refresh(invoice)
        assert payment.status == PaymentStatus.REFUNDED
        assert invoice.status == InvoiceStatus.REFUNDED