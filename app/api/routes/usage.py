from fastapi import APIRouter, Depends, HTTPException, Header, status

from app.dependencies.api_key import get_client_from_api_key
from app.schemas.usage import UsageEventCreate
from app.tasks.usage_tasks import process_usage_event


router = APIRouter(prefix="/usage-events", tags=["usage"])


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def track_usage(
    payload: UsageEventCreate,
    auth = Depends(get_client_from_api_key),
    idempotency_key: str | None = Header(None)
):

    client = auth["client"]
    api_key = auth["api_key"]

    if not idempotency_key:
        raise HTTPException(
            status_code=400,
            detail="Idempotency-Key header is required."
        )

    event = {
    "client_id": client.id,
    "project_id": client.project_id,
    "api_key_id": api_key.id,  
    "event_type": payload.event_type,
    "quantity": payload.quantity,
    "idempotency_key": idempotency_key,
    "metadata": payload.metadata
    }

    process_usage_event.delay(event)

    return {"status": "accepted"}