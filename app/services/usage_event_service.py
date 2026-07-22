from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.event_type import EventType
from app.tasks.usage_tasks import process_usage_event



class UsageEventService:
    
    @staticmethod
    def ingest_event(db: Session, event_code, project_id, client_id, api_key_id, quantity, idempotency_key, metadata):
        
        event_type = db.query(EventType).filter(
                EventType.project_id == project_id,
                EventType.event_code == event_code
            ).first()

        if not event_type:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Event type '{event_code}' is not registered for this project."
            )
        
        event = {
            "client_id": client_id,
            "project_id": project_id,
            "api_key_id": api_key_id,  
            "event_type_id": event_type.id,
            "quantity": quantity,
            "idempotency_key": idempotency_key,
            "metadata": metadata
        }

        process_usage_event.delay(event)
        

  

   

        



        
        
