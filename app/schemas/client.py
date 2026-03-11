from pydantic import BaseModel


class ClientCreate(BaseModel):
    project_id: int
    name: str
    email: str | None = None
    external_id: str | None = None

class ClientResponse(BaseModel):
    id: int
    name: str
    email: str
    external_id: str 

    class Config:
        from_attributes = True
