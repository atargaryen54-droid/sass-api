from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.deps import get_current_user

from app.schemas.api_key import ApiKeyCreate, ApiKeyResponse, ApiKeyRevokedResponse, ApiKeyUpdate
from app.services.api_key_service import ApiKeyService
from fastapi import HTTPException, status

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


@router.post("")
def create_api_key(
    payload: ApiKeyCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    return  ApiKeyService.create_api_key(
        db, user_id=current_user.id, 
        client_external_id=payload.client_external_id, 
        name = payload.name
        )

@router.get("/{client_external_id}", response_model=list[ApiKeyResponse])
def list_api_keys(
    client_external_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):

    return ApiKeyService.list_keys(
        db=db,
        user_id=current_user.id,
        client_external_id=client_external_id
    )

@router.post("/{api_key_external_id}/revoke", response_model=ApiKeyRevokedResponse)
def revoke_api_key(
    api_key_external_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return ApiKeyService.revoke_key(
        db=db,
        user_id=current_user.id,
        api_key_external_id=api_key_external_id,
    )

@router.post("/{api_key_external_id}/rotate")
def rotate_api_key(
    api_key_external_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return ApiKeyService.rotate_key(
        db=db,
        user_id=current_user.id,
        api_key_external_id=api_key_external_id,
    )

@router.patch("/{api_key_external_id}", response_model=ApiKeyResponse)
def update_api_key_name(
    api_key_external_id: str,
    payload: ApiKeyUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):

    return ApiKeyService.update_api_key(
        db=db,
        api_key_external_id=api_key_external_id,
        user_id = current_user.id,
        updates = payload.model_dump(exclude_unset=True)

    )
    
    
