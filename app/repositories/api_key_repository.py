from sqlalchemy.orm import Session
from app.models.api_key import ApiKey

class ApiKeyRepository:

    @staticmethod
    def create(db: Session, user_id: int, name: str, prefix: str, key_hash: str):

        key = ApiKey(
            user_id=user_id,
            name=name,
            key_prefix=prefix,
            key_hash=key_hash
        )

        db.add(key)
        db.commit()
        db.refresh(key)

        return key
