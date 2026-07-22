from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Optional, Dict


class UsageEventCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    
    event_code: str = Field(max_length=50)
    quantity: int = Field(gt=0)
    metadata: Optional[Dict] = None


    @field_validator("event_code")
    @classmethod
    def validate_event_code(cls, value: str) -> str:
        if not value:
            raise ValueError("event_code cannot be blank.")
        return value
