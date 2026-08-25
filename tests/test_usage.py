"""
Tests for UsageEventService.ingest_event (the synchronous, request-path
validation before an event is queued) and process_usage_event (the Celery
task that actually writes the row and handles idempotent retries).

ingest_event tests mock process_usage_event.delay so nothing here touches
Celery/Redis. process_usage_event tests call the task function directly
(Celery tasks remain plain callables outside the broker) against the real
test DB, since its dedup behavior depends on a real unique constraint
firing a real IntegrityError.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.models.user import User
from app.models.project import Project
from app.models.client import Client
from app.models.event_type import EventType
from app.models.api_key import ApiKey
from app.models.usage_event import UsageEvent
from app.schemas.enums import BillingFrequency, PaymentProvider
from app.services.usage_event_service import UsageEventService
from app.tasks.usage_tasks import process_usage_event


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


# ---------------------------------------------------------------------------
# UsageEventService.ingest_event
# ---------------------------------------------------------------------------

class TestIngestEvent:

    def test_unregistered_event_code_raises_404(self, db):
        project = make_project(db)
        client = make_client(db, project)
        api_key = make_api_key(db, client)

        with patch("app.services.usage_event_service.process_usage_event") as mock_task:
            with pytest.raises(HTTPException) as exc_info:
                UsageEventService.ingest_event(
                    db,
                    event_code="never_registered",
                    project_id=project.id,
                    client_id=client.id,
                    api_key_id=api_key.id,
                    quantity=1,
                    idempotency_key=str(uuid.uuid4()),
                    metadata=None,
                )
        assert exc_info.value.status_code == 404
        mock_task.delay.assert_not_called()

    def test_event_code_registered_for_a_different_project_still_404s(self, db):
        # event_type registration is per-project -- an event_code that
        # exists somewhere else must not be usable here.
        other_project = make_project(db)
        make_event_type(db, other_project, event_code="shared_code")

        project = make_project(db)
        client = make_client(db, project)
        api_key = make_api_key(db, client)

        with patch("app.services.usage_event_service.process_usage_event") as mock_task:
            with pytest.raises(HTTPException) as exc_info:
                UsageEventService.ingest_event(
                    db,
                    event_code="shared_code",
                    project_id=project.id,
                    client_id=client.id,
                    api_key_id=api_key.id,
                    quantity=1,
                    idempotency_key=str(uuid.uuid4()),
                    metadata=None,
                )
        assert exc_info.value.status_code == 404
        mock_task.delay.assert_not_called()

    def test_valid_event_enqueues_task_with_correct_payload(self, db):
        project = make_project(db)
        client = make_client(db, project)
        api_key = make_api_key(db, client)
        event_type = make_event_type(db, project, event_code="api_call")
        idempotency_key = str(uuid.uuid4())

        with patch("app.services.usage_event_service.process_usage_event") as mock_task:
            UsageEventService.ingest_event(
                db,
                event_code="api_call",
                project_id=project.id,
                client_id=client.id,
                api_key_id=api_key.id,
                quantity=7,
                idempotency_key=idempotency_key,
                metadata={"region": "eu"},
            )

        mock_task.delay.assert_called_once()
        (enqueued_event,), _ = mock_task.delay.call_args
        assert enqueued_event == {
            "client_id": client.id,
            "project_id": project.id,
            "api_key_id": api_key.id,
            "event_type_id": event_type.id,
            "quantity": 7,
            "idempotency_key": idempotency_key,
            "metadata": {"region": "eu"},
        }

    def test_no_row_is_written_synchronously_by_ingest_event(self, db):
        # ingest_event's job is to validate and enqueue -- the actual
        # UsageEvent row is only ever written by the worker task.
        project = make_project(db)
        client = make_client(db, project)
        api_key = make_api_key(db, client)
        make_event_type(db, project, event_code="api_call")

        with patch("app.services.usage_event_service.process_usage_event") as mock_task:
            UsageEventService.ingest_event(
                db,
                event_code="api_call",
                project_id=project.id,
                client_id=client.id,
                api_key_id=api_key.id,
                quantity=1,
                idempotency_key=str(uuid.uuid4()),
                metadata=None,
            )

        assert db.query(UsageEvent).filter(UsageEvent.client_id == client.id).count() == 0


# ---------------------------------------------------------------------------
# process_usage_event (the Celery task, called directly/synchronously)
# ---------------------------------------------------------------------------

def build_event(client, project, event_type, api_key, quantity=1, idempotency_key=None, metadata=None):
    return {
        "client_id": client.id,
        "project_id": project.id,
        "api_key_id": api_key.id,
        "event_type_id": event_type.id,
        "quantity": quantity,
        "idempotency_key": idempotency_key or str(uuid.uuid4()),
        "metadata": metadata,
    }


class TestProcessUsageEventTask:

    @pytest.fixture(autouse=True)
    def _route_task_session_to_test_db(self, db):
        """
        process_usage_event opens its own session via `SessionLocal()`
        from app.core.database rather than accepting one as a parameter --
        so left alone, it talks to settings.DATABASE_URL (the real/dev
        database), not the test database the `db` fixture and every other
        fixture in this file live in. Every insert would then reference a
        client_id/project_id/event_type_id that only exists in the test
        DB, fail as a foreign-key violation against the wrong database,
        and get silently swallowed by the task's overly-broad
        `except IntegrityError` -- logged as "duplicate ignored" even
        though nothing was ever a duplicate.

        Patch the task module's SessionLocal for the duration of each test
        here so it opens sessions against the same engine the `db`
        fixture uses.
        """
        test_session_factory = sessionmaker(
            bind=db.get_bind(), autocommit=False, autoflush=False
        )
        with patch("app.tasks.usage_tasks.SessionLocal", test_session_factory):
            yield

    def test_creates_usage_event_row_with_correct_fields(self, db):
        project = make_project(db)
        client = make_client(db, project)
        api_key = make_api_key(db, client)
        event_type = make_event_type(db, project)
        event = build_event(client, project, event_type, api_key, quantity=5, metadata={"k": "v"})

        process_usage_event(event)

        row = db.query(UsageEvent).filter(UsageEvent.client_id == client.id).first()
        assert row is not None
        assert row.quantity == 5
        assert row.event_metadata == {"k": "v"}
        assert row.idempotency_key == event["idempotency_key"]

    def test_duplicate_idempotency_key_for_same_client_is_silently_ignored(self, db):
        project = make_project(db)
        client = make_client(db, project)
        api_key = make_api_key(db, client)
        event_type = make_event_type(db, project)
        idempotency_key = str(uuid.uuid4())

        event = build_event(client, project, event_type, api_key, idempotency_key=idempotency_key)
        process_usage_event(event)
        # simulate Celery redelivering the same message
        process_usage_event(event)

        rows = db.query(UsageEvent).filter(
            UsageEvent.client_id == client.id, UsageEvent.idempotency_key == idempotency_key
        ).all()
        assert len(rows) == 1

    def test_same_idempotency_key_for_a_different_client_is_not_deduped(self, db):
        # the unique constraint is (client_id, idempotency_key) -- it's
        # per-client, not global, so this must NOT be treated as a dup.
        project = make_project(db)
        client_a = make_client(db, project)
        client_b = make_client(db, project)
        api_key_a = make_api_key(db, client_a)
        api_key_b = make_api_key(db, client_b)
        event_type = make_event_type(db, project)
        shared_key = str(uuid.uuid4())

        process_usage_event(build_event(client_a, project, event_type, api_key_a, idempotency_key=shared_key))
        process_usage_event(build_event(client_b, project, event_type, api_key_b, idempotency_key=shared_key))

        assert db.query(UsageEvent).filter(UsageEvent.idempotency_key == shared_key).count() == 2

    def test_unexpected_error_is_rolled_back_and_reraised_for_celery_retry(self, db):
        project = make_project(db)
        client = make_client(db, project)
        api_key = make_api_key(db, client)
        event_type = make_event_type(db, project)
        event = build_event(client, project, event_type, api_key)

        with patch("app.tasks.usage_tasks.UsageEvent", side_effect=RuntimeError("unexpected")):
            with pytest.raises(RuntimeError):
                process_usage_event(event)

        assert db.query(UsageEvent).filter(UsageEvent.client_id == client.id).count() == 0

