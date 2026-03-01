from sqlalchemy.orm import Session
from app.models.refresh_token import RefreshToken
from datetime import datetime, timezone

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

        return db.query(RefreshToken).filter(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked == False,
            RefreshToken.expires_at > datetime.now(timezone.utc)
        ).first()


    @staticmethod
    def revoke(db: Session, token: RefreshToken):

        token.revoked = True
        db.commit()
