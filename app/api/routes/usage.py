from fastapi import APIRouter, Depends

from app.dependencies.api_key import get_client_from_api_key

router = APIRouter(prefix="/usage-events", tags=["usage"])


@router.post("")
def track_usage(client = Depends(get_client_from_api_key)):

    return {
        "message": "Usage accepted",
        "client_id": client.id
    }
