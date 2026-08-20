from sqlalchemy.orm import Session
from app.models.api_key import ApiKey
from app.models.client import Client
from app.models.project import Project

class ApiKeyRepository:

    @staticmethod
    def create(db: Session, client_id: int, name: str, prefix: str, key_mask: str, key_hash: str):

        key = ApiKey(
            client_id=client_id,
            name=name,
            key_prefix=prefix,
            key_mask=key_mask,
            key_hash=key_hash
        )

        db.add(key)
        db.commit()
        db.refresh(key)

        return key
    
    @staticmethod
    def get_by_name_and_client(db: Session, name: str, client_id: int):
        return db.query(ApiKey).filter(
            ApiKey.client_id == client_id, 
            ApiKey.name == name,
            ApiKey.revoked == False
            ).first()
    
    @staticmethod
    def find_by_prefix(db: Session, prefix: str):

        return db.query(ApiKey).filter(
            ApiKey.key_prefix == prefix,
            ApiKey.revoked == False
        ).first()
    
    @staticmethod
    def get_by_client(db: Session, client_id: int):
        return (
            db.query(ApiKey)
            .filter(ApiKey.client_id == client_id)
            .order_by(ApiKey.created_at.desc())
            .all()
        )

    @staticmethod
    def get_by_external_id_and_user(db: Session, api_key_external_id: str, user_id: int):
        return(db.query(ApiKey)
            .join(Client, ApiKey.client_id == Client.id)
            .join(Project, Client.project_id == Project.id)
            .filter(
                ApiKey.external_id == api_key_external_id,
                Project.user_id == user_id).first()
        )


    
    

    
