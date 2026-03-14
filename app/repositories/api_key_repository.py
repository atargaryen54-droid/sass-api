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
    
