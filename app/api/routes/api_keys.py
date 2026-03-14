from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.deps import get_current_user

from app.schemas.api_key import ApiKeyCreate, ApiKeyResponse
from app.services.api_key_service import ApiKeyService
from app.repositories.api_key_repository import ApiKeyRepository
from app.repositories.client_repository import ClientRepository
from app.repositories.project_repository import ProjectRepository
from fastapi import HTTPException, status

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


@router.post("", response_model=ApiKeyResponse)
def create_api_key(
    payload: ApiKeyCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    ApiKeyService.verify_ownership(db, user_id=current_user.id, client_id=payload.client_id)
    

    raw_key, prefix, mask, hashed = ApiKeyService.generate_key()

    ApiKeyRepository.create(
        db=db,
        client_id=payload.client_id,
        name=payload.name,
        prefix=prefix,
        key_mask=mask,
        key_hash=hashed
    )

    return {"api_key": raw_key}
