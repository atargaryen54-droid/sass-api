from sqlalchemy.orm import Session
from app.models.event_type import EventType


class EventTypeRepository:

    @staticmethod
    def create(db: Session, project_id: int, event_code: str, event_name: str | None = None):
        
        event_type = EventType(
            project_id=project_id,
            event_code=event_code,
            event_name=event_name           
        )

        db.add(event_type)
        db.commit()
        db.refresh(event_type)

        return event_type
    
    def get_by_project_id(self, db: Session, project_id: int):
        return db.query(EventType).filter(
            EventType.project_id == project_id
            ).all()