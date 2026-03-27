from pydantic import BaseModel
from typing import Optional, Dict


class UsageEventCreate(BaseModel):
    event_type: str
    quantity: int = 1
    metadata: Optional[Dict] = None
