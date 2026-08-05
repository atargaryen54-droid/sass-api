
from fastapi import logger
from datetime import datetime, timezone
from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.services.billing_service import BillingService
from app.repositories.project_repository import ProjectRepository
from app.models.project import Project


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
                BillingService.generate_project_billing(project_db, project)
                success_count += 1
        except Exception:
            failure_count += 1
            logger.exception(f"Failed billing for project_id={project_id}")
        finally:
            project_db.close()

    return {
        "status": "completed",
        "successful": success_count,
        "failed": failure_count,
    }