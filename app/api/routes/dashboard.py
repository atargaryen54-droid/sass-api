from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.deps import get_current_user
from app.schemas.summary import SummaryResponse
from app.services.dashboard_service import DashboardService



router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.post("summary", response_model=SummaryResponse)
def get_summary(
        db: Session = Depends(get_db),
        user = Depends(get_current_user)
):
    
    summary = DashboardService.get_summary(db=db, user_id=user.id)

    return summary

