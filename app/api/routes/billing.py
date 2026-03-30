from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.deps import get_current_user

from app.services.billing_service import BillingService
from app.models.project import Project

router = APIRouter(prefix="/billing", tags=["billing"])
@router.get("/{project_id}")
def preview_billing(
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

    data = BillingService.calculate_usage(db, project_id)

    return {
        "project_id": project_id,
        "breakdown": data
    }
