from pydantic import BaseModel
from datetime import datetime

class ApiKeyCreate(BaseModel):
    client_external_id: str
    name: str

class ApiKeyResponse(BaseModel):
    external_id: str | None = None
    name: str
    key_prefix: str
    revoked: bool

    class Config:
        from_attributes = True

class ApiKeyRevokedResponse(BaseModel):
    external_id: str | None = None
    name: str
    key_prefix: str
    revoked: bool
    revoked_at: datetime | None = None
    revoked_by: int | None = None
    class Config:
        from_attributes = True

class ApiKeyUpdate(BaseModel):
    name: str | None = None
    