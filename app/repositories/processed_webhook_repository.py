from sqlalchemy.orm import Session
from app.models.processed_webhook import ProcessedWebhook

class ProcessedWebhookRepository:

    @staticmethod
    def create(db: Session, provider:str, event_id: str):
        processed_webhook = ProcessedWebhook(
            provider=provider,
            event_id=event_id
        )

        db.add(processed_webhook)
        db.commit()
        db.refresh(processed_webhook)

        return processed_webhook

    @staticmethod
    def  exists(db: Session, provider:str, event_id: str):
        
        return db.query(ProcessedWebhook).filter(
            ProcessedWebhook.provider == provider,
            ProcessedWebhook.event_id == event_id
        ).first() is not None


