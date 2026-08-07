from sqlalchemy.orm import Session
from app.models.user import User

class UserRepository:

    @staticmethod
    def get_by_email(db: Session, email: str):
        return db.query(User).filter(User.email == email).first()

    @staticmethod
    def create(
        db: Session, 
        email: str, 
        password_hash: str,
        full_name: str,
        company_name: str,
        timezone: str,
        default_currency: str
        ):
        user = User(
            email=email, 
            password_hash=password_hash,
            full_name=full_name,
            company_name=company_name,
            timezone=timezone,
            default_currency=default_currency
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
