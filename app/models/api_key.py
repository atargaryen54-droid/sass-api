import secrets
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.sql import func
from app.core.database import Base
from sqlalchemy.orm import relationship


def generate_short_id():
    return secrets.token_urlsafe(9)
class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)

    # make it not nullable later on
    external_id = Column(String, unique=True, index=True, default=generate_short_id, nullable=True)

    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)

    name = Column(String, nullable=False)

    key_prefix = Column(String, index=True, nullable=False)

    key_mask = Column(String, nullable=False )

    key_hash = Column(String, nullable=False)

    revoked = Column(Boolean, default=False)

    revoked_at = Column(DateTime(timezone=True), nullable=True)

    revoked_by = Column(Integer, nullable=True)

    client = relationship("Client", back_populates="api_keys")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
