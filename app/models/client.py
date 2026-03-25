from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.core.database import Base
from sqlalchemy.orm import relationship

class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)

    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)

    name = Column(String, nullable=False)

    email = Column(String, nullable=True)

    external_id = Column(String, nullable=True)

    api_keys = relationship("ApiKey", back_populates="client")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
