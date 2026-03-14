import secrets
from app.core.security import hash_token
from sqlalchemy.orm import Session
from app.repositories.client_repository import ClientRepository
from app.repositories.project_repository import ProjectRepository
from fastapi import HTTPException, status

class ApiKeyService:

    @staticmethod
    def generate_key():

        raw = "sk_live_" + secrets.token_urlsafe(32)

        prefix = raw[:12]

        mask = raw[-4:]

        hashed = hash_token(raw)

        return raw, prefix, mask, hashed
    
    @staticmethod
    def verify_ownership(db: Session, user_id: int, client_id: int):

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
        return None

   

    


