from pydantic import BaseModel

class ApiKeyCreate(BaseModel):
    client_id: int
    name: str

class ApiKeyResponse(BaseModel):
    api_key: str
