from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.deps import get_current_user

from app.schemas.pricing import PricingRuleCreate, PricingRuleResponse, PricingSummary
from app.repositories.pricing_repository import PricingRepository
from app.models.project import Project

router = APIRouter(prefix="/pricing", tags=["pricing"])

@router.post("", response_model=PricingRuleResponse)
def create_pricing_rule(
    payload: PricingRuleCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    project = db.query(Project).filter(
        Project.id == payload.project_id,
        Project.user_id == user.id
    ).first()

    if not project:
        raise HTTPException(status_code=403, detail="Not allowed")

    rule = PricingRepository.create(
        db=db,
        project_id=payload.project_id,
        event_type=payload.event_type,
        price=payload.price_per_unit
    )

    return rule

@router.get("/{project_id}", response_model=list[PricingSummary])
def list_pricing_rules(
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

    return PricingRepository.get_by_project(db, project_id)
