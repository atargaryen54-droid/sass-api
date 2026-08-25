import logging
from sqlalchemy.exc import IntegrityError
from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.usage_event import UsageEvent

logger = logging.getLogger(__name__)


def is_duplicate_error(exc: IntegrityError) -> bool:
    """Checks if the IntegrityError is caused by a unique constraint/duplicate entry violation."""
    orig = getattr(exc, "orig", None)
    if not orig:
        return False

    # PostgreSQL (psycopg2 / psycopg3 check via sqlstate or string)
    sqlstate = getattr(orig, "pgcode", getattr(orig, "sqlstate", None))
    if sqlstate == "23505":  # 23505 is PostgreSQL unique_violation code
        return True

    # Generic string checks for SQLite / MySQL / PostgreSQL string outputs
    err_msg = str(orig).lower()
    return "unique constraint" in err_msg or "duplicate key" in err_msg or "duplicate entry" in err_msg


@celery_app.task
def process_usage_event(event: dict):
    db = SessionLocal()

    try:
        usage = UsageEvent(
            project_id=event["project_id"],
            client_id=event["client_id"],
            api_key_id=event["api_key_id"],
            event_type_id=event["event_type_id"],
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

    except IntegrityError as exc:
        db.rollback()

        if is_duplicate_error(exc):
            logger.info(
                "Duplicate usage event ignored",
                extra={
                    "client_id": event["client_id"],
                    "idempotency_key": event["idempotency_key"]
                }
            )
            return

        # Re-raise non-duplicate IntegrityErrors (e.g. Foreign Key failures, NOT NULL checks)
        logger.exception(
            "Integrity constraint violation (non-duplicate) while processing usage event.",
            extra={
                "client_id": event.get("client_id"),
                "idempotency_key": event.get("idempotency_key") 
            }
        )
        raise

    except Exception:
        db.rollback()
        logger.exception("Failed processing usage event.")
        raise

    finally:
        db.close()