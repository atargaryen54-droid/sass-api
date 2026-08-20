from sqlalchemy.orm import Session, joinedload
from app.models.client import Client
from app.models.project import Project


class ClientRepository:

    @staticmethod
    def create(db: Session, project_id: int, name: str, email: str):

        client = Client(
            project_id=project_id,
            name=name,
            email=email
        )

        db.add(client)
        db.commit()
        db.refresh(client)

        return client

    @staticmethod
    def get_by_id(db: Session, client_id: int):
        return db.query(Client).filter(Client.id == client_id).first()

    @staticmethod
    def get_by_external_id_and_user(db: Session, client_external_id: str, user_id: int):
        return(
            db.query(Client)
            .join(Client.project)
            .filter(
                Client.external_id == client_external_id,
                Project.user_id == user_id
            ).first()
        ) 
    
    @staticmethod
    def get_by_email_and_project(db: Session, email: str, project_id: int):
        return db.query(Client).filter(
            Client.project_id == project_id, 
            Client.email == email
            ).first()

    @staticmethod
    def list_by_project(db: Session, project_id: int) -> list[Client]:
        return (
            db.query(Client)
            .join(Client.project)
            .filter(
                Client.project_id == project_id
            )
            .all()
        )

    @staticmethod
    def list_all_for_user(db: Session, user_id: int) -> list[Client]:
        return (
            db.query(Client)
            .join(Client.project)
            .options(
                joinedload(Client.project)
            )
            .filter(Project.user_id == user_id)
            .all()
        )
