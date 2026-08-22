"""
Tests for WebhookService.process_stripe_event and its per-event handlers.

Two design decisions get the most scrutiny here, because they're easy to
"clean up" by accident later and both matter for correctness:

1. An event already recorded in ProcessedWebhookRepository short-circuits
   before any handler runs -- this is what makes webhook delivery safe to
   retry.
2. An unhandled event *type* (at the top level) or an unhandled refund
   *status* (inside handle_refund_updated) does NOT get a ProcessedWebhook
   record written for it. This is deliberate: if we don't yet know how to
   handle something, we want Stripe to keep redelivering it once we do,
   rather than have it silently marked "processed" and never revisited.

"""

import uuid
from datetime import datetime, timezone
from unittest.mock import patch

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
from app.services.webhook_service import WebhookService
from app.repositories.processed_webhook_repository import ProcessedWebhookRepository


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


def stripe_event(event_type, object_payload, event_id=None):
    return {
        "id": event_id or f"evt_{uuid.uuid4().hex[:12]}",
        "type": event_type,
        "data": {"object": object_payload},
    }


def is_processed(db, event_id, provider="stripe"):
    return ProcessedWebhookRepository.exists(db, provider=provider, event_id=event_id)


# ---------------------------------------------------------------------------
# process_stripe_event: idempotency + routing
# ---------------------------------------------------------------------------

class TestProcessStripeEventRouting:

    def test_already_processed_event_short_circuits_before_any_handler_runs(self, db):
        event_id = f"evt_{uuid.uuid4().hex[:12]}"
        ProcessedWebhookRepository.create(db, provider="stripe", event_id=event_id)

        event = stripe_event(
            "payment_intent.succeeded", {"id": "pi_whatever"}, event_id=event_id
        )

        with patch.object(WebhookService, "handle_payment_succeeded") as mock_handler:
            WebhookService.process_stripe_event(db, event)

        mock_handler.assert_not_called()

    def test_unhandled_event_type_does_not_get_marked_processed(self, db):
        event = stripe_event("charge.dispute.created", {"id": "dp_1"})

        # must not raise, even though nothing recognizes this event type
        WebhookService.process_stripe_event(db, event)

        assert is_processed(db, event["id"]) is False

    def test_routes_payment_succeeded_events_to_handle_payment_succeeded(self, db):
        payment = make_payment(db, status=PaymentStatus.INITIATED)
        event = stripe_event(
            "payment_intent.succeeded", {"id": payment.provider_payment_id}
        )

        WebhookService.process_stripe_event(db, event)

        db.refresh(payment)
        assert payment.status == PaymentStatus.SUCCEEDED
        assert is_processed(db, event["id"]) is True

    def test_routes_refund_updated_events_to_handle_refund_updated(self, db):
        payment = make_payment(db, status=PaymentStatus.SUCCEEDED)
        refund = make_refund(db, payment, amount=100.0, status=RefundStatus.PENDING)
        event = stripe_event(
            "refund.updated", {"id": refund.provider_refund_id, "status": "cancelled"}
        )

        WebhookService.process_stripe_event(db, event)

        db.refresh(refund)
        assert refund.status == RefundStatus.CANCELLED
        assert is_processed(db, event["id"]) is True


# ---------------------------------------------------------------------------
# handle_payment_succeeded
# ---------------------------------------------------------------------------

class TestHandlePaymentSucceeded:

    def test_marks_payment_succeeded_and_invoice_paid(self, db):
        # invoice must already be PENDING -- that's what create_payment sets
        # before a payment can ever reach Stripe, so it's the only invoice
        # status a real "payment succeeded" webhook would ever see.
        invoice = make_invoice(db, status=InvoiceStatus.PENDING)
        payment = make_payment(db, status=PaymentStatus.INITIATED, invoice=invoice)
        event = stripe_event("payment_intent.succeeded", {"id": payment.provider_payment_id})

        WebhookService.process_stripe_event(db, event)

        db.refresh(payment)
        db.refresh(invoice)
        assert payment.status == PaymentStatus.SUCCEEDED
        assert invoice.status == InvoiceStatus.PAID

    def test_idempotent_if_payment_already_succeeded(self, db):
        invoice = make_invoice(db, status=InvoiceStatus.PAID)
        payment = make_payment(db, status=PaymentStatus.SUCCEEDED, invoice=invoice)
        event = stripe_event("payment_intent.succeeded", {"id": payment.provider_payment_id})

        # must not raise (invoice is already PAID -- a second PAID
        # transition attempt would be illegal if it were even attempted)
        WebhookService.process_stripe_event(db, event)

        db.refresh(payment)
        db.refresh(invoice)
        assert payment.status == PaymentStatus.SUCCEEDED
        assert invoice.status == InvoiceStatus.PAID
        # the early-return path skips create_processed_webhook_record entirely
        assert is_processed(db, event["id"]) is False

    def test_unknown_payment_is_a_no_op(self, db):
        event = stripe_event("payment_intent.succeeded", {"id": "pi_does_not_exist"})

        WebhookService.process_stripe_event(db, event)

        assert is_processed(db, event["id"]) is False


# ---------------------------------------------------------------------------
# handle_payment_failed
# ---------------------------------------------------------------------------

class TestHandlePaymentFailed:

    def test_marks_payment_failed_and_records_processed_webhook(self, db):
        payment = make_payment(db, status=PaymentStatus.INITIATED)
        event = stripe_event("payment_intent.payment_failed", {"id": payment.provider_payment_id})

        WebhookService.process_stripe_event(db, event)

        db.refresh(payment)
        assert payment.status == PaymentStatus.FAILED
        assert is_processed(db, event["id"]) is True

    def test_failure_reason_from_stripe_payload_is_used(self, db):

        payment = make_payment(db, status=PaymentStatus.INITIATED)
        event = stripe_event(
            "payment_intent.payment_failed",
            {
                "id": payment.provider_payment_id,
                "last_payment_error": {"message": "Your card was declined."},
            },
        )

        WebhookService.process_stripe_event(db, event)

        db.refresh(payment)
        assert payment.status == PaymentStatus.FAILED
        assert payment.failure_reason == "Your card was declined." 

    def test_unknown_payment_is_a_no_op(self, db):
        event = stripe_event("payment_intent.payment_failed", {"id": "pi_does_not_exist"})

        WebhookService.process_stripe_event(db, event)

        assert is_processed(db, event["id"]) is False


# ---------------------------------------------------------------------------
# handle_payment_canceled
# ---------------------------------------------------------------------------

class TestHandlePaymentCanceled:

    def test_marks_payment_cancelled_and_records_processed_webhook(self, db):
        payment = make_payment(db, status=PaymentStatus.INITIATED)
        event = stripe_event("payment_intent.canceled", {"id": payment.provider_payment_id})

        WebhookService.process_stripe_event(db, event)

        db.refresh(payment)
        assert payment.status == PaymentStatus.CANCELLED
        assert is_processed(db, event["id"]) is True

    def test_unknown_payment_is_a_no_op(self, db):
        event = stripe_event("payment_intent.canceled", {"id": "pi_does_not_exist"})

        WebhookService.process_stripe_event(db, event)

        assert is_processed(db, event["id"]) is False


# ---------------------------------------------------------------------------
# handle_refund_updated
# ---------------------------------------------------------------------------

class TestHandleRefundUpdated:

    def test_succeeded_status_cascades_when_fully_refunded(self, db):
        invoice = make_invoice(db, status=InvoiceStatus.PAID, total_amount=100.0)
        payment = make_payment(db, status=PaymentStatus.SUCCEEDED, amount=100.0, invoice=invoice)
        refund = make_refund(db, payment, amount=100.0, status=RefundStatus.PENDING)
        event = stripe_event(
            "refund.updated", {"id": refund.provider_refund_id, "status": "succeeded"}
        )

        WebhookService.process_stripe_event(db, event)

        db.refresh(refund)
        db.refresh(payment)
        db.refresh(invoice)
        assert refund.status == RefundStatus.SUCCEEDED
        assert payment.status == PaymentStatus.REFUNDED
        assert invoice.status == InvoiceStatus.REFUNDED
        assert is_processed(db, event["id"]) is True

    def test_failed_status_sets_failure_reason_from_payload(self, db):
        # unlike handle_payment_failed, this handler uses dict .get() --
        # so the payload's failure_reason is genuinely captured here.
        payment = make_payment(db, status=PaymentStatus.SUCCEEDED)
        refund = make_refund(db, payment, amount=100.0, status=RefundStatus.PENDING)
        event = stripe_event(
            "refund.updated",
            {
                "id": refund.provider_refund_id,
                "status": "failed",
                "failure_reason": "expired_or_canceled_card",
            },
        )

        WebhookService.process_stripe_event(db, event)

        db.refresh(refund)
        assert refund.status == RefundStatus.FAILED
        assert refund.failure_reason == "expired_or_canceled_card"

    def test_cancelled_status_transitions_refund(self, db):
        payment = make_payment(db, status=PaymentStatus.SUCCEEDED)
        refund = make_refund(db, payment, amount=100.0, status=RefundStatus.PENDING)
        event = stripe_event(
            "refund.updated", {"id": refund.provider_refund_id, "status": "cancelled"}
        )

        WebhookService.process_stripe_event(db, event)

        db.refresh(refund)
        assert refund.status == RefundStatus.CANCELLED

    def test_unhandled_refund_status_does_not_transition_or_get_marked_processed(self, db):
        payment = make_payment(db, status=PaymentStatus.SUCCEEDED)
        refund = make_refund(db, payment, amount=100.0, status=RefundStatus.PENDING)
        event = stripe_event(
            "refund.updated", {"id": refund.provider_refund_id, "status": "requires_action"}
        )

        WebhookService.process_stripe_event(db, event)

        db.refresh(refund)
        assert refund.status == RefundStatus.PENDING  # untouched
        assert is_processed(db, event["id"]) is False  # left open for redelivery

    def test_unknown_refund_is_a_no_op(self, db):
        event = stripe_event(
            "refund.updated", {"id": "re_does_not_exist", "status": "succeeded"}
        )

        WebhookService.process_stripe_event(db, event)

        assert is_processed(db, event["id"]) is False