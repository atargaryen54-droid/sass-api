from sqlalchemy.orm import Session
from app.models.client import Client


class ClientRepository:

    @staticmethod
    def create(db: Session, project_id: int, name: str, email: str | None,    external_id: str | None):

        client = Client(
            project_id=project_id,
            name=name,
            email=email,
            external_id=external_id
        )

        db.add(client)
        db.commit()
        db.refresh(client)

        return client

    @staticmethod
    def get_by_id(db: Session, client_id: int):
        return db.query(Client).filter(Client.id == client_id).first()
    
    @staticmethod
    def get_by_name_and_project(db: Session, name: str, project_id: int):
        return db.query(Client).filter(
            Client.project_id == project_id, 
            Client.name == name
            ).first()
