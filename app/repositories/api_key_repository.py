from sqlalchemy.orm import Session
from app.models.api_key import ApiKey

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
            ApiKey.name == name
            ).first()
    
    @staticmethod
    def find_by_prefix(db: Session, prefix: str):

        return db.query(ApiKey).filter(
            ApiKey.key_prefix == prefix,
            ApiKey.revoked == False
        ).first()

    
