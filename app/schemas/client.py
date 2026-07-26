from pydantic import BaseModel


class ClientCreate(BaseModel):
    project_id: int
    name: str
    email: str | None = None
    external_id: str | None = None

class ClientResponse(BaseModel):
    external_id: str 
    name: str
    email: str


    class Config:
        from_attributes = True
