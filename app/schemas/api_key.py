from pydantic import BaseModel
from datetime import datetime

class ApiKeyCreate(BaseModel):
    client_id: int
    name: str

class ApiKeyResponse(BaseModel):
    id: int
    name: str
    key_prefix: str
    revoked: bool
    created_at: datetime

    class Config:
        from_attributes = True

class ApiKeyRevokedResponse(BaseModel):
    id: int
    name: str
    key_prefix: str
    revoked: bool
    revoked_at: datetime | None = None
    revoked_by: int | None = None

    class Config:
        from_attributes = True
