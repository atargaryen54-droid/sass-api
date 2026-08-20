from sqlalchemy.orm import Session
from app.repositories.project_repository import ProjectRepository
from app.repositories.client_repository import ClientRepository
from fastapi import HTTPException, status
from app.schemas.client import ClientsByProject

class ClientService:

    @staticmethod
    def create_client(
        db: Session, 
        project_external_id: str, 
        user_id: int, 
        name: str, 
        email: str,
    ):
   
        name = name.lower()
        project = ProjectRepository.get_by_external_id_and_user(
            db, project_external_id=project_external_id,
            user_id=user_id)
        
        if project is None:
            raise HTTPException(status_code=404, detail="Project/service not found")
                       
        if ClientRepository.get_by_email_and_project(db, email = email, project_id = project.id ) is not None:
            raise HTTPException(
            status_code=409, 
            detail=f"Client with email '{email}' already exists for this service."
        )

        client = ClientRepository.create(
            db=db,
            project_id=project.id,
            name=name,
            email=email
        )
        return client

    @staticmethod
    def get_client_by_id(db: Session, client_external_id: int, user_id: int):
        client = ClientRepository.get_by_external_id_and_user(
            db, 
            client_external_id=client_external_id,
            user_id=user_id
            )

        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Client with ID {client_external_id} not found."
            )
        return client


    @staticmethod
    def list_clients(db: Session, user_id: int, project_external_id: str | None=None) -> list[ClientsByProject]:
        if project_external_id:
            project = ProjectRepository.get_by_external_id_and_user(
                db, project_external_id=project_external_id, user_id=user_id
            )
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")

            clients = ClientRepository.list_by_project(db, project_id=project.id)

            if not clients:
                return [ClientsByProject(
                    project_external_id=project.external_id,
                    project_name=project.name,
                    clients=[]
                )]

            return [ClientsByProject(
                project_external_id=project.external_id,
                project_name=project.name,
                clients=clients
            )]

        # no filter -> group across all of the user's project
        clients = ClientRepository.list_all_for_user(db, user_id=user_id)

        grouped: dict[int, ClientsByProject] = {}
        for client in clients:
            pid = client.project.id
            if pid not in grouped:
                grouped[pid] = ClientsByProject(
                    project_external_id=client.project.external_id,
                    project_name=client.project.name,
                    clients=[]
                )
            grouped[pid].clients.append(client)

        return list(grouped.values())


    @staticmethod
    def update_client(db: Session, user_id:int, client_external_id:str, updates:dict):

        client = ClientRepository.get_by_external_id_and_user(
            db=db, 
            client_external_id=client_external_id, 
            user_id=user_id
            )
        
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Client with ID {client_external_id} not found."
            )
        for field,value in updates.items():
            setattr(client, field, value)

        db.commit()
        db.refresh(client)

        return client
    
    @staticmethod
    def delete_client(db:Session, user_id:int, client_external_id:str):
        client = ClientRepository.get_by_external_id_and_user(
                    db=db, 
                    client_external_id=client_external_id, 
                    user_id=user_id
                    )
                
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Client with ID {client_external_id} not found."
            )
        
        db.delete(client)
        db.commit()
        return {"detail": f"client with ID {client_external_id} has been deleted"}



        
        

    


    



    
