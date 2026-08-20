from sqlalchemy.orm import Session
from app.models.pricing_rule import PricingRule
from app.models.event_type import EventType
from app.models.project import Project


class PricingRuleRepository:

    @staticmethod
    def create(db: Session, event_type_id: int, price_per_unit: float):
        pricing_rule = PricingRule(
            event_type_id=event_type_id,
            price_per_unit=price_per_unit
        )

        db.add(pricing_rule)
        db.commit()
        db.refresh(pricing_rule)

        return pricing_rule

    @staticmethod
    def get_by_project_id(db: Session, project_id: int):
        return (
            db.query(PricingRule)
            .join(EventType, PricingRule.event_type_id == EventType.id)
            .filter(EventType.project_id == project_id)
            .all()
        )

    @staticmethod
    def get_by_external_id_and_user(db: Session, pricing_rule_external_id: str, user_id: int):
        return (
            db.query(PricingRule)
            .join(EventType, PricingRule.event_type_id == EventType.id)
            .join(Project, EventType.project_id == Project.id)
            .filter(
                PricingRule.external_id == pricing_rule_external_id,
                Project.user_id == user_id
            ).first()
        )

    @staticmethod
    def get_active_by_event_type(db: Session, event_type_id: int):
        return (
            db.query(PricingRule)
            .filter(PricingRule.event_type_id == event_type_id)
            .first()
        )