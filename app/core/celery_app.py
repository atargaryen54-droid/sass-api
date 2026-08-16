from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

celery_app = Celery(
    "worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.usage_tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

celery_app.conf.imports = [
    "app.tasks.scheduler_tasks",
]

# 3. Add the Beat Schedule
celery_app.conf.beat_schedule = {
    # Production schedule: runs every night at 2:00 AM UTC
    "generate-due-invoices-nightly": {
        "task": "app.tasks.scheduler_tasks.generate_due_invoices",
        "schedule": crontab(hour=2, minute=0),
    },

    "reconcile-payments-and-refunds-every-3-minutes": {
        "task": "app.tasks.scheduler_tasks.reconcile_with_provider",
        "schedule": 180.0

    }
    

    # # TEMPORARY TEST SCHEDULE (Uncomment to test every 30 seconds):
    # "test-generate-invoices-every-30-seconds": {
    #     "task": "app.tasks.scheduler_tasks.generate_due_invoices",
    #     "schedule": 30.0,
    # },
}
