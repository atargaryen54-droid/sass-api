"""
Tests for RefundStatusService (the status state machine) and
RefundService.create_refund (payment-status guards, default-to-full-amount,
over-refund rejection, and the remaining-balance calculation across
multiple partial refunds).

create_refund is called directly against the real test DB. The provider is
always mocked via PaymentProviderFactory.get so nothing here touches the
network.
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
from app.services.refund_service import RefundService
from app.services.refund_status_service import RefundStatusService


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


def make_payment(db, status=PaymentStatus.SUCCEEDED, amount=100.0, invoice=None):
    invoice = invoice or make_invoice(db, total_amount=amount)
    payment = Payment(
        invoice_id=invoice.id,
        provider=PaymentProvider.STRIPE,
        amount=amount,
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


FAKE_PROVIDER_REFUND_RESULT = {"provider_refund_id": "re_fake_123", "status": "pending"}


# ---------------------------------------------------------------------------
# RefundStatusService: pure state machine, no DB needed.
# ---------------------------------------------------------------------------

def build_refund(status: RefundStatus):
    return Refund(status=status.value)


class TestRefundStatusTransitions:

    @pytest.mark.parametrize(
        "from_status,to_status",
        [
            (RefundStatus.CREATED, RefundStatus.PENDING),
            (RefundStatus.CREATED, RefundStatus.FAILED),
            (RefundStatus.CREATED, RefundStatus.CANCELLED),
            (RefundStatus.PENDING, RefundStatus.SUCCEEDED),
            (RefundStatus.PENDING, RefundStatus.FAILED),
            (RefundStatus.PENDING, RefundStatus.CANCELLED),
            (RefundStatus.FAILED, RefundStatus.PENDING),
            (RefundStatus.FAILED, RefundStatus.CANCELLED),
        ],
    )
    def test_allowed_transitions_succeed(self, from_status, to_status):
        refund = build_refund(from_status)
        result = RefundStatusService.transition_status(refund, to_status)
        assert result is True
        assert refund.status == to_status

    @pytest.mark.parametrize(
        "from_status,to_status",
        [
            (RefundStatus.CREATED, RefundStatus.SUCCEEDED),
            (RefundStatus.PENDING, RefundStatus.CREATED),
            (RefundStatus.FAILED, RefundStatus.SUCCEEDED),
            (RefundStatus.SUCCEEDED, RefundStatus.PENDING),
            (RefundStatus.SUCCEEDED, RefundStatus.FAILED),
            (RefundStatus.SUCCEEDED, RefundStatus.CANCELLED),
            (RefundStatus.CANCELLED, RefundStatus.PENDING),
            (RefundStatus.CANCELLED, RefundStatus.SUCCEEDED),
        ],
    )
    def test_disallowed_transitions_raise_and_do_not_mutate(self, from_status, to_status):
        refund = build_refund(from_status)
        with pytest.raises(ValueError):
            RefundStatusService.transition_status(refund, to_status)
        assert refund.status == from_status

    @pytest.mark.parametrize(
        "status",
        [
            RefundStatus.CREATED,
            RefundStatus.PENDING,
            RefundStatus.SUCCEEDED,
            RefundStatus.FAILED,
            RefundStatus.CANCELLED,
        ],
    )
    def test_same_status_transition_is_a_no_op(self, status):
        refund = build_refund(status)
        result = RefundStatusService.transition_status(refund, status)
        assert result is False
        assert refund.status == status


# ---------------------------------------------------------------------------
# RefundService.create_refund
# ---------------------------------------------------------------------------

class TestCreateRefund:

    def test_rejects_payment_that_is_not_succeeded(self, db):
        payment = make_payment(db, status=PaymentStatus.PROCESSING, amount=100.0)

        with pytest.raises(HTTPException) as exc_info:
            RefundService.create_refund(
                db, user_id=payment.invoice.project.user_id,
                payment_external_id=payment.external_id,
                requested_amount=None, reason=None,
            )
        assert exc_info.value.status_code == 422

    def test_rejects_payment_already_fully_refunded(self, db):
        payment = make_payment(db, status=PaymentStatus.REFUNDED, amount=100.0)

        with pytest.raises(HTTPException) as exc_info:
            RefundService.create_refund(
                db, user_id=payment.invoice.project.user_id,
                payment_external_id=payment.external_id,
                requested_amount=None, reason=None,
            )
        assert exc_info.value.status_code == 422

    def test_no_amount_defaults_to_full_remaining_balance(self, db):
        payment = make_payment(db, status=PaymentStatus.SUCCEEDED, amount=100.0)

        with patch("app.payment.provider_factory.PaymentProviderFactory.get") as mock_get:
            mock_get.return_value.create_refund.return_value = FAKE_PROVIDER_REFUND_RESULT

            RefundService.create_refund(
                db, user_id=payment.invoice.project.user_id,
                payment_external_id=payment.external_id,
                requested_amount=None, reason=None,
            )

        refunds = db.query(Refund).filter(Refund.payment_id == payment.id).all()
        assert len(refunds) == 1
        assert float(refunds[0].amount) == pytest.approx(100.0)

    def test_no_amount_defaults_to_remaining_balance_after_a_prior_partial_refund(self, db):
        payment = make_payment(db, status=PaymentStatus.SUCCEEDED, amount=100.0)
        make_refund(db, payment, amount=30.0, status=RefundStatus.SUCCEEDED)

        with patch("app.payment.provider_factory.PaymentProviderFactory.get") as mock_get:
            mock_get.return_value.create_refund.return_value = FAKE_PROVIDER_REFUND_RESULT

            RefundService.create_refund(
                db, user_id=payment.invoice.project.user_id,
                payment_external_id=payment.external_id,
                requested_amount=None, reason=None,
            )

        new_refund = (
            db.query(Refund)
            .filter(Refund.payment_id == payment.id, Refund.amount != 30.0)
            .first()
        )
        assert float(new_refund.amount) == pytest.approx(70.0)

    def test_requested_amount_over_remaining_balance_is_rejected(self, db):
        payment = make_payment(db, status=PaymentStatus.SUCCEEDED, amount=100.0)
        make_refund(db, payment, amount=60.0, status=RefundStatus.SUCCEEDED)

        with pytest.raises(HTTPException) as exc_info:
            RefundService.create_refund(
                db, user_id=payment.invoice.project.user_id,
                payment_external_id=payment.external_id,
                requested_amount=50.0,  # only 40.0 remains
                reason=None,
            )
        assert exc_info.value.status_code == 422

        refunds = db.query(Refund).filter(Refund.payment_id == payment.id).all()
        assert len(refunds) == 1  # the one we seeded -- the rejected request created nothing

    @pytest.mark.parametrize("bad_amount", [0, -10.0])
    def test_zero_or_negative_amount_is_rejected(self, db, bad_amount):
        payment = make_payment(db, status=PaymentStatus.SUCCEEDED, amount=100.0)

        with pytest.raises(HTTPException) as exc_info:
            RefundService.create_refund(
                db, user_id=payment.invoice.project.user_id,
                payment_external_id=payment.external_id,
                requested_amount=bad_amount, reason=None,
            )
        assert exc_info.value.status_code == 422

    def test_partial_refund_within_remaining_balance_succeeds(self, db):
        payment = make_payment(db, status=PaymentStatus.SUCCEEDED, amount=100.0)
        make_refund(db, payment, amount=60.0, status=RefundStatus.SUCCEEDED)

        with patch("app.payment.provider_factory.PaymentProviderFactory.get") as mock_get:
            mock_get.return_value.create_refund.return_value = FAKE_PROVIDER_REFUND_RESULT

            result = RefundService.create_refund(
                db, user_id=payment.invoice.project.user_id,
                payment_external_id=payment.external_id,
                requested_amount=40.0,  # exactly what remains
                reason="customer request",
            )

        assert result["status"] == RefundStatus.PENDING

    def test_provider_failure_rolls_back_and_reraises(self, db):
        payment = make_payment(db, status=PaymentStatus.SUCCEEDED, amount=100.0)

        with patch("app.payment.provider_factory.PaymentProviderFactory.get") as mock_get:
            mock_get.return_value.create_refund.side_effect = RuntimeError("stripe down")

            with pytest.raises(RuntimeError):
                RefundService.create_refund(
                    db, user_id=payment.invoice.project.user_id,
                    payment_external_id=payment.external_id,
                    requested_amount=None, reason=None,
                )

        refunds = db.query(Refund).filter(Refund.payment_id == payment.id).all()
        assert refunds == []  # rolled back, nothing persisted

    def test_pending_refund_is_counted_against_remaining_balance(self, db):
    
        payment = make_payment(db, status=PaymentStatus.SUCCEEDED, amount=100.0)
        # a refund already in flight, not yet confirmed by the provider
        make_refund(db, payment, amount=90.0, status=RefundStatus.PENDING)

        with patch("app.payment.provider_factory.PaymentProviderFactory.get") as mock_get:
            mock_get.return_value.create_refund.return_value = FAKE_PROVIDER_REFUND_RESULT

            # checking to see if it would create another
            # near full refund while the above near full
            # refund is pending and awaiting confirmation
            # from the provider
            with pytest.raises(HTTPException) as exc_info:
                result = RefundService.create_refund(
                    db, user_id=payment.invoice.project.user_id,
                    payment_external_id=payment.external_id,
                    requested_amount=90.0,
                    reason=None,
                )
            assert exc_info.value.status_code == 422


        refunds = db.query(Refund).filter(Refund.payment_id == payment.id).all()
        assert len(refunds) == 1
        assert sum(float(r.amount) for r in refunds) == pytest.approx(90.0)  

    def test_raises_404_for_unknown_payment(self, db):
        user = make_user(db)
        with pytest.raises(HTTPException) as exc_info:
            RefundService.create_refund(
                db, user_id=user.id,
                payment_external_id="does-not-exist",
                requested_amount=None, reason=None,
            )
        assert exc_info.value.status_code == 404