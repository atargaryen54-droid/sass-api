from pydantic import BaseModel, ConfigDict, EmailStr


class ClientCreate(BaseModel):
    project_external_id: str
    name: str
    email: EmailStr


class ClientResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    external_id: str 
    name: str
    email: EmailStr

class ClientsByProject(BaseModel):
    project_external_id: str
    project_name: str
    clients: list[ClientResponse]


    class Config:
        from_attributes = True

class ClientUpdate(BaseModel):
    name: str | None=None
    email: str | None=None
