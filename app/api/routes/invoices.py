from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.api.deps import get_db
from app.api.deps import get_current_user
from app.services.billing_service import BillingService
from app.models.project import Project

router = APIRouter(prefix="/invoices", tags=["invoices"])

@router.post("/{project_id}")
def generate_invoices(
    project_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == user.id
    ).first()

    if not project:
        raise HTTPException(status_code=403, detail="Not allowed")

    # for now: full range
    period_start = datetime(2025, 1, 1)
    period_end = datetime.now(timezone.utc)

    invoices = BillingService.generate_invoices(
        db,
        project_id,
        period_start,
        period_end
    )

    return {
        "created": len(invoices)
    }
