from sqlalchemy.orm import Session
from app.repositories.project_repository import ProjectRepository
from app.repositories.event_type_repository import EventTypeRepository
from fastapi import HTTPException, status
from app.schemas.event_type import EventTypesByProject

class EventTypeService:

    @staticmethod
    def create_event_type(
        db: Session, 
        project_external_id: str, 
        user_id: int, 
        name: str, 
        event_code: str,
    ):
   
        name = name.lower()
        project = ProjectRepository.get_by_external_id_and_user(
            db, project_external_id=project_external_id,
            user_id=user_id)
        
        if project is None:
            raise HTTPException(status_code=404, detail="Project/service not found")
                       
        if EventTypeRepository.get_by_event_code_and_project(
            db, 
            event_code = event_code, 
            project_id = project.id ) is not None:
                
                raise HTTPException(
                status_code=409, 
                detail=f"EventType with code '{event_code}' already exists for this service."
            )

        event_type = EventTypeRepository.create(
            db=db,
            project_id=project.id,
            event_code=event_code,
            name=name
        )
        return event_type

    @staticmethod
    def get_event_type_by_id(db: Session, event_type_external_id: str, user_id: int):
        event_type = EventTypeRepository.get_by_external_id_and_user(
            db, 
            event_type_external_id=event_type_external_id,
            user_id=user_id
            )

        if not event_type:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Event Type with ID {event_type_external_id} not found."
            )
        return event_type


    @staticmethod
    def list_event_types(db: Session, user_id: int, project_external_id: str) -> list[EventTypesByProject]:
        
        project = ProjectRepository.get_by_external_id_and_user(
            db, project_external_id=project_external_id, user_id=user_id
        )
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        event_types = EventTypeRepository.get_by_project_id(db=db, project_id=project.id)

        if not event_types:
            return [EventTypesByProject(
                project_external_id=project.external_id,
                project_name=project.name,
                event_types=[]
            )]

        return [EventTypesByProject(
            project_external_id=project.external_id,
            project_name=project.name,
            event_types=event_types
        )]

    @staticmethod
    def update_event_type(db: Session, user_id:int, event_type_external_id:str, updates:dict):

        event_type = EventTypeRepository.get_by_external_id_and_user(
            db=db, 
            event_type_external_id=event_type_external_id, 
            user_id=user_id
            )
        
        if not event_type:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Event Type with ID {event_type_external_id} not found."
            )
        for field,value in updates.items():
            setattr(event_type, field, value)

        db.commit()
        db.refresh(event_type)

        return event_type
    
    @staticmethod
    def delete_event_type(db: Session, user_id:int, event_type_external_id: str):
        event_type = EventTypeRepository.get_by_external_id_and_user(
            db=db, 
            event_type_external_id=event_type_external_id, 
            user_id=user_id
            )
    
        if not event_type:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Event Type with ID {event_type_external_id} not found."
                    )
        
        db.delete(event_type)
        db.commit()
        return {"detail": f"Event type with ID {event_type_external_id} has been deleted"}



        
        

    


    



    
