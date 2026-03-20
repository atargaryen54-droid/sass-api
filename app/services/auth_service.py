from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.repositories.user_repository import UserRepository
from app.core.security import verify_password, create_access_token, create_refresh_token
from datetime import datetime, timedelta, timezone
from app.core.security import hash_token
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.core.config import settings
from app.core.security import decode_token, verify_token_hash


class AuthService:

    @staticmethod
    def login(db: Session, email: str, password: str):

        email = email.lower()
        user = UserRepository.get_by_email(db, email)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )

        if not verify_password(password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        RefreshTokenRepository.revoke_all_for_user(db, user.id)
        access_token = create_access_token(str(user.id))
        refresh_token = create_refresh_token(str(user.id))

        expires_at = datetime.now(timezone.utc) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )

        RefreshTokenRepository.create(
            db=db,
            user_id=user.id,
            token_hash=hash_token(refresh_token),
            expires_at=expires_at
        )


        return {
            "access_token": access_token,
            "refresh_token": refresh_token
        }
    from app.core.security import decode_token, verify_token_hash


    @staticmethod
    def refresh(db: Session, refresh_token: str):
        payload = decode_token(refresh_token)
        
        if not payload or payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid refresh token")

        user_id = int(payload.get("sub"))
        stored = RefreshTokenRepository.get_valid_token(db, user_id)

        if not stored:
            raise HTTPException(
                status_code=401, 
                detail="Token not found"
            )    
        
        if not verify_token_hash(refresh_token, stored.token_hash):
            raise HTTPException(
                status_code=401, 
                detail="Invalid token"
            )

        RefreshTokenRepository.revoke_all_for_user(db, user_id)

        new_access = create_access_token(str(user_id))
        new_refresh = create_refresh_token(str(user_id))
        expires_at = datetime.now(timezone.utc) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )

        RefreshTokenRepository.create(
            db, user_id, hash_token(new_refresh), expires_at
        )

        return {
            "access_token": new_access,
            "refresh_token": new_refresh,
            "token_type": "bearer"
        }
    

    @staticmethod
    def logout(db: Session, refresh_token: str):

        payload = decode_token(refresh_token)

        if not payload or payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid refresh token")

        user_id = int(payload.get("sub"))

        stored = RefreshTokenRepository.get_valid_token(db, user_id)

        if not stored:
            raise HTTPException(status_code=401, detail="Token not found")

        if not verify_token_hash(refresh_token, stored.token_hash):
            raise HTTPException(status_code=401, detail="Invalid token")

        RefreshTokenRepository.revoke_all_for_user(db, user_id)

        return {"message": "Logged out successfully"}

