import secrets
from datetime import datetime
from app.core.security import hash_token
from sqlalchemy.orm import Session
from app.models.api_key import ApiKey
from app.repositories.client_repository import ClientRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.api_key_repository import ApiKeyRepository
from fastapi import HTTPException, status
from app.models.client import Client
from app.models.project import Project

class ApiKeyService:
    
    @staticmethod
    def create_api_key(db: Session, user_id: int, client_id: int, name: str):
        
        # name = name.lower()

        if (client := ClientRepository.get_by_id(db, client_id)):
            client_project_id = client.project_id
        else:
            raise HTTPException(status_code=404, detail="Client not found")
        
        client_project = ProjectRepository.get_by_id(db, client_project_id)
        
        if client_project.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to create keys for this client"
            )

        if ApiKeyRepository.get_by_name_and_client(db, name = name, client_id = client_id ) is not None:
            raise HTTPException(
            status_code=409, 
            detail=f"active api-key with name '{name}' already exists for this client."
        )
        
        
        raw_key, prefix, mask, hashed = ApiKeyService.generate_key()

        ApiKeyRepository.create(
            db=db,
            client_id=client_id,
            name=name,
            prefix=prefix,
            key_mask=mask,
            key_hash=hashed
        )
        return raw_key
    
    @staticmethod
    def generate_key():

        raw = "sk_live_" + secrets.token_urlsafe(32)

        prefix = raw[:12]

        mask = raw[-4:]

        hashed = hash_token(raw)

        return raw, prefix, mask, hashed
    
    @staticmethod
    def list_keys(db: Session, user_id: int, client_id: int):

        client = (
            db.query(Client)
            .join(Project, Client.project_id == Project.id)
            .filter(
                Client.id == client_id,
                Project.user_id == user_id,
            )
            .first()
        )

        if not client:
            raise HTTPException(
                status_code=404,
                detail="Client not found."
            )

        return ApiKeyRepository.get_by_client(db, client_id)
    
    @staticmethod
    def revoke_key(db: Session, user_id: int,api_key_id: int):

        api_key = (
            db.query(ApiKey)
            .join(Client, ApiKey.client_id == Client.id)
            .join(Project, Client.project_id == Project.id)
            .filter(
                ApiKey.id == api_key_id,
                Project.user_id == user_id
            )
            .first()
        )

        if not api_key:
            raise HTTPException(
                status_code=404,
                detail="API key not found."
            )

        if not api_key.revoked:
            api_key.revoked = True
            api_key.revoked_at = datetime.now()
            db.commit()
        return api_key
    

   

    

