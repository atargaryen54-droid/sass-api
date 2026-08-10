from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from app.core.database import Base
import secrets

def generate_short_id():
    return secrets.token_urlsafe(9)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    external_id = Column(String, unique=True, nullable=False, default=generate_short_id)

    full_name = Column(String, nullable=False)

    company_name = Column(String, nullable=False)

    timezone = Column(String, nullable=False, default='UTC')

    default_currency = Column(String, nullable=False, default='USD')

    email = Column(String, unique=True, index=True, nullable=False)

    password_hash = Column(String, nullable=False)

    is_active = Column(Boolean, default=True)

    is_verified = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
