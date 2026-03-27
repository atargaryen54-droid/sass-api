from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.usage_event import UsageEvent


@celery_app.task
def process_usage_event(event: dict):

    db = SessionLocal()

    try:
        usage = UsageEvent(
            project_id=event["project_id"],
            client_id=event["client_id"],
            api_key_id=event["api_key_id"],
            event_type=event["event_type"],
            quantity=event["quantity"],
            event_metadata=event.get("metadata")
        )

        db.add(usage)
        db.commit()

    finally:
        db.close()

