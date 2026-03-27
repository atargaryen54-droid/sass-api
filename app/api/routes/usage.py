from fastapi import APIRouter, Depends

from app.dependencies.api_key import get_client_from_api_key
from app.schemas.usage import UsageEventCreate

router = APIRouter(prefix="/usage-events", tags=["usage"])


@router.post("")
def track_usage(
    payload: UsageEventCreate,
    client = Depends(get_client_from_api_key)
):

    event = {
    "client_id": client.id,
    "project_id": client.project_id,
    "api_key_id": client.api_keys[0].id,  
    "event_type": payload.event_type,
    "quantity": payload.quantity,
    "metadata": payload.metadata
    }

    return {"status": "accepted"}