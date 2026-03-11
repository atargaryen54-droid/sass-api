from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.deps import get_current_user

from app.schemas.api_key import ApiKeyCreate, ApiKeyResponse
from app.services.api_key_service import ApiKeyService
from app.repositories.api_key_repository import ApiKeyRepository

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


@router.post("", response_model=ApiKeyResponse)
def create_api_key(
    payload: ApiKeyCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    raw_key, prefix, hashed = ApiKeyService.generate_key()

    ApiKeyRepository.create(
        db=db,
        user_id=user.id,
        name=payload.name,
        prefix=prefix,
        key_hash=hashed
    )

    return {"api_key": raw_key}
