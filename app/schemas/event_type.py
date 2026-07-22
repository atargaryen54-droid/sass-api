from pydantic import BaseModel


class EventTypeCreate(BaseModel):
    project_id: int
    event_code: str
    event_name: str | None = None


class EventTypeResponse(BaseModel):
    id: int
    project_id: int
    event_code: str
    event_name: str | None = None

    class Config:
        from_attributes = True
