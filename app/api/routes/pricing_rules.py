from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.deps import get_current_user
from app.schemas.pricing_rule import PricingRuleCreate, PricingRuleResponse, PricingRuleUpdate, PricingRulesByProject
from app.services.pricing_rule_service import PricingRuleService


router = APIRouter(prefix="/pricing_rules", tags=["pricing_rules"])


@router.post("", response_model=PricingRuleResponse)
def create_pricing_rule(
    payload: PricingRuleCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    pricing_rule = PricingRuleService.create_pricing_rule(
        db,
        event_type_external_id=payload.event_type_external_id,
        user_id=current_user.id,
        price_per_unit=payload.price_per_unit
    )
    return pricing_rule

@router.get("/{pricing_rule_external_id}", response_model=PricingRuleResponse)
def get_pricing_rule(
    pricing_rule_external_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    pricing_rule = PricingRuleService.get_pricing_rule_by_id(
        db,
        pricing_rule_external_id=pricing_rule_external_id,
        user_id=current_user.id
    )
    return pricing_rule

@router.get("", response_model=list[PricingRulesByProject])
def list_pricing_rules(
    project_external_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    return PricingRuleService.list_pricing_rules(
        db,
        user_id=current_user.id,
        project_external_id=project_external_id
    )

@router.patch("/{pricing_rule_external_id}", response_model=PricingRuleResponse)
def update_pricing_rule(
    pricing_rule_external_id: str,
    payload: PricingRuleUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    return PricingRuleService.update_pricing_rule(
        db=db,
        user_id=current_user.id,
        pricing_rule_external_id=pricing_rule_external_id,
        updates=payload.model_dump(exclude_unset=True)
    )

@router.delete("/{pricing_rule_external_id}")
def delete_pricing_rule(
    pricing_rule_external_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    return PricingRuleService.delete_pricing_rule(
        db=db,
        user_id=current_user.id,
        pricing_rule_external_id=pricing_rule_external_id
    )