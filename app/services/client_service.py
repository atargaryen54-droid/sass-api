from sqlalchemy.orm import Session
from app.repositories.project_repository import ProjectRepository
from app.repositories.client_repository import ClientRepository
from fastapi import HTTPException, status

class ClientService:

    @staticmethod
    def create_client(db: Session, project_id: int, user_id: int, name: str, email: str, external_id: str):
   
        name = name.lower()
        project = ProjectRepository.get_by_id(db, project_id)
        
        if project is None:
            raise HTTPException(status_code=404, detail="Project/service not found")
                       
        if project.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to create a client for this project/service"
            )
        if ClientRepository.get_by_name_and_project(db, name = name, project_id = project_id ) is not None:
            raise HTTPException(
            status_code=409, 
            detail=f"Client '{name}' already exists for this service."
        )


        client = ClientRepository.create(
            db=db,
            project_id=project_id,
            name=name,
            email=email,
            external_id=external_id
        )

        
        return client



    
