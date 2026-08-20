from sqlalchemy.orm import Session
from sqlalchemy import DateTime
from app.models.project import Project
from app.schemas.enums import PaymentProvider, BillingFrequency


class ProjectRepository:

    @staticmethod
    def create(
        db: Session, 
        user_id: int, 
        name: str,
        payment_provider:  PaymentProvider,
        billing_frequency: BillingFrequency,
        next_billing_date: DateTime
        ):

        project = Project(
            user_id=user_id,
            name=name,
            payment_provider=payment_provider,
            billing_frequency=billing_frequency,
            next_billing_date=next_billing_date
        )

        db.add(project)
        db.commit()
        db.refresh(project)

        return project
    
    @staticmethod
    def get_by_id(db: Session, project_id: int):
        return (
            db.query(Project).filter(Project.id == project_id).first()
        )
    
    @staticmethod
    def get_by_external_id_and_user(db: Session, project_external_id: str, user_id: int):
        return (
            db.query(Project).filter(
                Project.external_id == project_external_id, 
                Project.user_id == user_id).first()
        )

    @staticmethod
    def list_by_user(db: Session, user_id: int):
        return db.query(Project).filter(Project.user_id == user_id).all()

    @staticmethod
    def get_by_name_and_user(db: Session, name: str, user_id: int):

        return db.query(Project).filter(
            Project.user_id == user_id, 
            Project.name == name
            ).first()

    @staticmethod
    def get_projects_due_for_billing(db: Session, current_time):
        
        return db.query(Project.id).filter(
            Project.next_billing_date.is_not(None),
            Project.next_billing_date <= current_time
        ).all()

