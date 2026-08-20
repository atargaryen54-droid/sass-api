from sqlalchemy.orm import Session
from app.repositories.event_type_repository import EventTypeRepository
from app.repositories.pricing_rule_repository import PricingRuleRepository
from app.repositories.project_repository import ProjectRepository
from fastapi import HTTPException, status
from app.schemas.pricing_rule import PricingRulesByProject

class PricingRuleService:

    @staticmethod
    def create_pricing_rule(
        db: Session,
        event_type_external_id: str,
        user_id: int,
        price_per_unit: float,
    ):
        event_type = EventTypeRepository.get_by_external_id_and_user(
            db, event_type_external_id=event_type_external_id,
            user_id=user_id)

        if event_type is None:
            raise HTTPException(status_code=404, detail="Event type not found")

        if PricingRuleRepository.get_active_by_event_type(
            db, event_type_id=event_type.id) is not None:

                raise HTTPException(
                status_code=409,
                detail="A pricing rule already exists for this event type."
            )

        pricing_rule = PricingRuleRepository.create(
            db=db,
            event_type_id=event_type.id,
            price_per_unit=price_per_unit
        )
        return pricing_rule

    @staticmethod
    def get_pricing_rule_by_id(db: Session, pricing_rule_external_id: str, user_id: int):
        pricing_rule = PricingRuleRepository.get_by_external_id_and_user(
            db,
            pricing_rule_external_id=pricing_rule_external_id,
            user_id=user_id
            )

        if not pricing_rule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pricing rule with ID {pricing_rule_external_id} not found."
            )
        return pricing_rule

    @staticmethod
    def list_pricing_rules(db: Session, user_id: int, project_external_id: str) -> list[PricingRulesByProject]:

        project = ProjectRepository.get_by_external_id_and_user(
            db, project_external_id=project_external_id, user_id=user_id
        )
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        pricing_rules = PricingRuleRepository.get_by_project_id(db=db, project_id=project.id)

        return [
            PricingRulesByProject(
                project_external_id=project.external_id,
                project_name=project.name,
                event_code=pricing_rule.event_code,
                pricing_rule=pricing_rule
            )
            for pricing_rule in pricing_rules
        ]

    @staticmethod
    def update_pricing_rule(db: Session, user_id:int, pricing_rule_external_id:str, updates:dict):

        pricing_rule = PricingRuleRepository.get_by_external_id_and_user(
            db=db,
            pricing_rule_external_id=pricing_rule_external_id,
            user_id=user_id
            )

        if not pricing_rule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pricing rule with ID {pricing_rule_external_id} not found."
            )
        for field,value in updates.items():
            setattr(pricing_rule, field, value)

        db.commit()
        db.refresh(pricing_rule)

        return pricing_rule

    @staticmethod
    def delete_pricing_rule(db: Session, user_id:int, pricing_rule_external_id: str):
        pricing_rule = PricingRuleRepository.get_by_external_id_and_user(
            db=db,
            pricing_rule_external_id=pricing_rule_external_id,
            user_id=user_id
            )

        if not pricing_rule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pricing rule with ID {pricing_rule_external_id} not found."
                    )

        db.delete(pricing_rule)
        db.commit()
        return {"detail": f"Pricing rule with ID {pricing_rule_external_id} has been deleted"}