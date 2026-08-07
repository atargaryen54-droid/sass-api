from sqlalchemy.orm import Session
from app.repositories.user_repository import UserRepository
from app.core.security import hash_password
from fastapi import HTTPException, status

class UserService:

    @staticmethod
    def register_user(
        db: Session, 
        email: str, 
        password: str, 
        full_name: str, 
        company_name: str,
        timezone: str,
        default_currency: str
        ):
    
        email = email.lower()
        existing = UserRepository.get_by_email(db, email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )

        password_hash = hash_password(password)
        return UserRepository.create(
            db=db, 
            email=email, 
            password_hash=password_hash,
            full_name=full_name,
            company_name=company_name,
            timezone=timezone,
            default_currency=default_currency
            )
