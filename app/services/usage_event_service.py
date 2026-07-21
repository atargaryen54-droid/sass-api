from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.event_type import EventType



class UsageEventService:
    
    @staticmethod
    def check_event(db: Session, event_code: str, project_id: int):
        
        event_type = db.query(EventType).filter(
                EventType.project_id == project_id,
                EventType.event_code == event_code
            ).first()

        if not event_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Event type '{event_code}' is not registered for this project."
            )

        return event_type.id



        
        
