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
