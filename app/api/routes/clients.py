from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.deps import get_current_user

from app.schemas.client import ClientCreate, ClientResponse
from app.repositories.client_repository import ClientRepository
from app.services.client_service import ClientService


router = APIRouter(prefix="/clients", tags=["clients"])


@router.post("", response_model=ClientResponse)
def create_client(
    payload: ClientCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    client = ClientService.create_client(
        db, 
        project_id = payload.project_id,
        user_id = current_user.id,
        name = payload.name,
        email = payload.email,
        external_id=payload.external_id
        )

    return client


