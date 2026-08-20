from pydantic import BaseModel, ConfigDict


class EventTypeCreate(BaseModel):
    project_external_id: str
    event_code: str
    event_name: str | None = None


class EventTypeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    external_id: str
    name: str | None = None
    event_code: str
   



class EventTypeUpdate(BaseModel):
    event_name: str | None=None
    event_code: str | None=None

class EventTypesByProject(BaseModel):
    project_external_id: str
    project_name: str
    event_types: list[EventTypeResponse]

    class Config:
        from_attributes = True
