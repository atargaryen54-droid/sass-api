from pydantic import BaseModel, ConfigDict
from datetime import datetime

class ApiKeyCreate(BaseModel):
    client_external_id: str
    name: str

class ApiKeyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    external_id: str | None = None
    name: str
    key_prefix: str
    revoked: bool


class ApiKeyRevokedResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    external_id: str | None = None
    name: str
    key_prefix: str
    revoked: bool
    revoked_at: datetime | None = None
    revoked_by: int | None = None

class ApiKeyUpdate(BaseModel):
    name: str | None = None
