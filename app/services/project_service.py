from sqlalchemy.orm import Session
from app.repositories.project_repository import ProjectRepository
from fastapi import HTTPException, status
from app.schemas.enums import BillingFrequency
from dateutil.relativedelta import relativedelta
from datetime import datetime, timezone

class ProjectService:



    @staticmethod
    def calculate_next_billing_date(billing_frequency: BillingFrequency):
        current_time = datetime.now(timezone.utc)
        
        if billing_frequency == BillingFrequency.MONTHLY:
            return current_time + relativedelta(months=1)
        
        elif billing_frequency == BillingFrequency.WEEKLY:
            return current_time + relativedelta(weeks=1)
    
        elif billing_frequency == BillingFrequency.DAILY:
            return current_time + relativedelta(days=1)

    @staticmethod
    def create_project(db:Session, name, user_id, payment_provider, billing_frequency):

        name = name.lower()

        if ProjectRepository.get_by_name_and_user(db, name = name, user_id = user_id ) is not None:
            raise HTTPException(
            status_code=409, 
            detail=f"Service '{name}' already exists for the user."
        )

        next_billing_date = ProjectService.calculate_next_billing_date(billing_frequency)

        project = ProjectRepository.create(
            db=db,
            user_id=user_id,
            name=name,
            payment_provider=payment_provider,
            billing_frequency=billing_frequency,
            next_billing_date=next_billing_date
        )
        return project
    

    def get_project_by_external_id(db: Session, project_external_id: str, user_id: int):
        project = ProjectRepository.get_by_external_id_and_user(
            db, 
            project_external_id=project_external_id, 
            user_id=user_id)

        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project with ID {project_external_id} not found."
            )
        return project
    

    def list_projects(db: Session, user_id: int):
        projects = ProjectRepository.list_by_user(db, user_id=user_id)
        return projects


    def update_project(db: Session, project_external_id: str, user_id: int, updates: dict):
        project = ProjectRepository.get_by_external_id_and_user(
            db, 
            project_external_id=project_external_id, 
            user_id=user_id)

        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project with ID {project_external_id} not found."
            )
        if 'billing_frequency' in updates:
            updates['next_billing_date'] = ProjectService.calculate_next_billing_date(updates['billing_frequency'])

        for field, value in updates.items():
            setattr(project, field, value)

        db.commit()
        db.refresh(project)
        return project
    

    def delete_project(db: Session, project_external_id: str, user_id: int):
        project = ProjectRepository.get_by_external_id_and_user(
            db, 
            project_external_id=project_external_id, 
            user_id=user_id)

        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project with ID {project_external_id} not found."
            )

        db.delete(project)
        db.commit()
        return {"detail": f"Project with ID {project_external_id} has been deleted."}
    
    
