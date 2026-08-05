from sqlalchemy.orm import Session
from app.models.project import Project


class ProjectRepository:

    @staticmethod
    def create(db: Session, user_id: int, name: str):

        project = Project(
            user_id=user_id,
            name=name
        )

        db.add(project)
        db.commit()
        db.refresh(project)

        return project
    
    @staticmethod
    def get_by_id(db: Session, project_id: int):
        return db.query(Project).filter(Project.id == project_id).first()
    
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
