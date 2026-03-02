from sqlalchemy.orm import Session
from app.models.refresh_token import RefreshToken
from datetime import datetime, timezone
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from fastapi import HTTPException

class RefreshTokenRepository:

    @staticmethod
    def create(db: Session, user_id: int, token_hash: str, expires_at):

        token = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at
        )

        db.add(token)
        db.commit()
        db.refresh(token)

        return token


    @staticmethod
    def get_valid_token(db: Session, user_id: int):
        try:
            token = db.query(RefreshToken).filter(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked == False,
                RefreshToken.expires_at > datetime.now(timezone.utc)
            ).with_for_update(nowait=True).first()
            
            return token

        except OperationalError as e:
            db.rollback() 
            raise HTTPException(
                status_code=429, 
                detail="Concurrent token request detected. Please try again."
            )


    @staticmethod
    def revoke_all_for_user(db: Session, user_id: int):
        db.query(RefreshToken).filter(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked == False
        ).update({"revoked": True})
        db.commit()

    
