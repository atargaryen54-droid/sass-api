from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.sql import func
from app.core.database import Base

class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    name = Column(String, nullable=False)

    key_prefix = Column(String, index=True)

    key_hash = Column(String, nullable=False, index=True, unique=True)

    revoked = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

