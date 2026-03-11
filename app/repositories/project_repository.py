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
