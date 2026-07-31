import secrets
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.core.database import Base
from app.schemas.enums import PaymentProvider



def generate_short_id():
    return secrets.token_urlsafe(9)


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)

    external_id = Column(String, unique=True, nullable=False, default=generate_short_id)

    payment_provider = Column(String, nullable=False, default=PaymentProvider.STRIPE )

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    name = Column(String, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
 