from sqlalchemy.orm import Session
from app.models.event_type import EventType
from app.models.project import Project


class EventTypeRepository:

    @staticmethod
    def create(db: Session, project_id: int, event_code: str, name: str | None = None):
        
        event_type = EventType(
            project_id=project_id,
            event_code=event_code,
            name=name           
        )

        db.add(event_type)
        db.commit()
        db.refresh(event_type)

        return event_type
    
    @staticmethod
    def get_by_project_id(db: Session, project_id: int):
        return db.query(EventType).filter(
            EventType.project_id == project_id
            ).all()

    @staticmethod
    def get_by_external_id_and_user(db: Session, event_type_external_id: str, user_id: int):
        return(
            db.query(EventType)
            .join(Project, EventType.project_id == Project.id)
            .filter(
                EventType.external_id == event_type_external_id,
                Project.user_id == user_id
            ).first()
        ) 

    @staticmethod
    def get_by_event_code_and_project(db: Session, event_code: str, project_id: int):
        return(      
            db.query(EventType)
            .join(Project, EventType.project_id == Project.id)
            .filter(
                Project.id == project_id,
                EventType.event_code == event_code
            ).first()
        )