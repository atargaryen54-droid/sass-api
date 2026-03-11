from pydantic import BaseModel

class ApiKeyCreate(BaseModel):
    name: str

class ApiKeyResponse(BaseModel):
    api_key: str
