from sqlalchemy.orm import Session
from app.models.pricing_rule import PricingRule


class PricingRepository:

    @staticmethod
    def create(db: Session, project_id: int, event_type: str, price: float):

        rule = PricingRule(
            project_id=project_id,
            event_type=event_type,
            price_per_unit=price
        )

        db.add(rule)
        db.commit()
        db.refresh(rule)

        return rule


    @staticmethod
    def get_by_project(db: Session, project_id: int):

        return db.query(PricingRule).filter(
            PricingRule.project_id == project_id
        ).all()
