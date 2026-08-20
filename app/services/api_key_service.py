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
    def create_api_key(db: Session, user_id: int, client_external_id: str, name: str):
        
        name = name.lower()

        client = ClientRepository.get_by_external_id_and_user(
            db=db, 
            client_external_id=client_external_id,
            user_id=user_id
            )
        if not client:
            raise HTTPException(
                status_code=404, 
                detail="Client not found")
        

        if ApiKeyRepository.get_by_name_and_client(db, name = name, client_id = client.id ) is not None:
            raise HTTPException(
            status_code=409, 
            detail=f"active api-key with name '{name}' already exists for this client."
        )
        
        
        raw_key, prefix, mask, hashed = ApiKeyService.generate_key()

        new_api_key = ApiKeyRepository.create(
                db=db,
                client_id=client.id,
                name=name,
                prefix=prefix,
                key_mask=mask,
                key_hash=hashed
        )

        return {
            "external_id": new_api_key.external_id,
            "name": name,
            "api_key": raw_key
        }
    
    @staticmethod
    def generate_key():

        raw = "sk_live_" + secrets.token_urlsafe(32)

        prefix = raw[:12]

        mask = raw[-4:]

        hashed = hash_token(raw)

        return raw, prefix, mask, hashed
    
    @staticmethod
    def list_keys(db: Session, user_id: int, client_external_id: int):

        client = ClientRepository.get_by_external_id_and_user(
                    db=db, 
                    client_external_id=client_external_id,
                    user_id=user_id
                    )
        if not client:
            raise HTTPException(
                status_code=404,
                detail="Client not found."
            )

        return ApiKeyRepository.get_by_client(db, client.id)
    
    @staticmethod
    def revoke_key(db: Session, user_id: int,api_key_external_id: str):

        api_key = ApiKeyRepository.get_by_external_id_and_user(
            db=db,
            user_id = user_id,
            api_key_external_id=api_key_external_id,
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
    
    @staticmethod
    def rotate_key(db: Session, user_id: int, api_key_external_id: str):
        
        api_key = ApiKeyRepository.get_by_external_id_and_user(
            db=db,
            user_id = user_id,
            api_key_external_id=api_key_external_id,
        )
        
        if not api_key:
            raise HTTPException(
                status_code=404,
                detail="API key not found."
            )
        
        if api_key.revoked:
            raise HTTPException(
                status_code=400,
                detail="Cannot rotate a revoked API key."
            )
        
        raw_key, prefix, mask, hashed = ApiKeyService.generate_key()

        new_key = ApiKey(
            client_id=api_key.client_id,
            name=api_key.name,
            key_prefix=prefix,
            key_mask=mask,
            key_hash=hashed
        )

        api_key.revoked = True
        api_key.revoked_at = datetime.now()

        db.add(new_key)
        db.commit()
        db.refresh(new_key)

        return {

            "message": "API key rotated successfully.",
            "api_key": raw_key 
        }

    @staticmethod
    def update_api_key(db: Session, api_key_external_id: str, user_id: int, updates:dict):
        api_key = ApiKeyRepository.get_by_external_id_and_user(
            db=db,
            user_id = user_id,
            api_key_external_id=api_key_external_id,
        )
        if not api_key:
            raise HTTPException(
                status_code=404,
                detail="API key not found."
            )
        for field,value in updates.items():
            setattr(api_key, field, value)

        db.commit()
        db.refresh(api_key)

        return api_key

        




    

   

    

