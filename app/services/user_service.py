from sqlalchemy.orm import Session
from app.repositories.user_repository import UserRepository
from app.core.security import hash_password
from fastapi import HTTPException, status

class UserService:

    @staticmethod
    def register_user(db: Session, email: str, password: str):
        existing = UserRepository.get_by_email(db, email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )

        password_hash = hash_password(password)
        return UserRepository.create(db, email, password_hash)
