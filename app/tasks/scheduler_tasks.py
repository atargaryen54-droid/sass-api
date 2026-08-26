import logging
from datetime import datetime, timezone
from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from redis import Redis
from app.repositories.project_repository import ProjectRepository
from app.models.project import Project
from app.services.reconcilliation_service import ReconciliationService
from app.services.invoice_service import InvoiceService
from app.core.config import settings


logger = logging.getLogger(__name__)
redis_client = Redis.from_url(settings.REDIS_URL)

@celery_app.task
def generate_due_invoices():
    db = SessionLocal()

    try:
        # Fetch only IDs/lightweight records to keep session scope clean
        due_project_ids = ProjectRepository.get_projects_due_for_billing(
            db=db, current_time=datetime.now(timezone.utc)
        )
        project_ids = [p_id for (p_id,) in due_project_ids]

    finally:
        db.close()

    success_count = 0
    failure_count = 0

    # Process each project in its own isolated session
    for project_id in project_ids:
        project_db = SessionLocal()
        try:
            project = project_db.query(Project).get(project_id)
            if project:
                InvoiceService.generate_project_billing(project_db, project)
                success_count += 1
        except Exception:
            failure_count += 1
            logger.exception(f"Failed billing for project_id={project.external_id}")
        finally:
            project_db.close()

    return {
        "status": "completed",
        "successful": success_count,
        "failed": failure_count,
    }


@staticmethod
def run_reconciliation():
    with SessionLocal() as db:
                ReconciliationService.reconcile_payments(db)
                ReconciliationService.reconcile_refunds(db)
                
@celery_app.task(name="app.tasks.scheduler_tasks.reconcile_with_provider")
def reconcile_with_provider():
    # Acquire a 2-minute lock
    lock = redis_client.lock("reconcile_provider_lock", timeout=120)
    
    # Acquires lock non-blockingly; if another worker holds it, skip this cycle
    if not lock.acquire(blocking=False):
        logging.info("Reconciliation task already running in another worker. Skipping.")
        return

    try:
         run_reconciliation()
    finally:
        lock.release()



