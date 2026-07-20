from sqlalchemy.exc import IntegrityError

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.usage_event import UsageEvent
import logging

logger = logging.getLogger(__name__)


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
            event_metadata=event.get("metadata"),
            idempotency_key=event["idempotency_key"]
        )

        db.add(usage)
        db.commit()


        logger.info(
            "Processed usage event",
            extra={
                "client_id": event["client_id"],
                "idempotency_key": event["idempotency_key"]
            }
        )

    except IntegrityError:

        db.rollback()

        logger.info(
            "Duplicate usage event ignored",
            extra={
                "client_id": event["client_id"],
                "idempotency_key": event["idempotency_key"]
            }
        )

        return
    
    except Exception:

        db.rollback()

        logger.exception("Failed processing usage event.")

        raise


    finally:
        db.close()

