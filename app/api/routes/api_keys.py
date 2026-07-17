from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.deps import get_current_user

from app.schemas.api_key import ApiKeyCreate, ApiKeyResponse, ApiKeyRevokedResponse
from app.services.api_key_service import ApiKeyService
from fastapi import HTTPException, status

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


@router.post("", response_model=ApiKeyResponse)
def create_api_key(
    payload: ApiKeyCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    raw_key = ApiKeyService.create_api_key(db, user_id=current_user.id, client_id=payload.client_id, name = payload.name)
    

    return {"api_key": raw_key}

@router.get("/{client_id}", response_model=list[ApiKeyResponse])
def list_api_keys(
    client_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):

    return ApiKeyService.list_keys(
        db=db,
        user_id=current_user.id,
        client_id=client_id
    )

@router.post("/{api_key_id}/revoke", response_model=ApiKeyRevokedResponse)
def revoke_api_key(
    api_key_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return ApiKeyService.revoke_key(
        db=db,
        user_id=current_user.id,
        api_key_id=api_key_id,
    )
