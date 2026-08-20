from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.deps import get_current_user

from app.schemas.client import ClientCreate, ClientResponse
from app.repositories.client_repository import ClientRepository
from app.services.client_service import ClientService
from app.schemas.client import ClientsByProject
from app.schemas.client import ClientUpdate


router = APIRouter(prefix="/clients", tags=["clients"])


@router.post("", response_model=ClientResponse)
def create_client(
    payload: ClientCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    client = ClientService.create_client(
        db, 
        project_external_id = payload.project_external_id,
        user_id = current_user.id,
        name = payload.name,
        email = payload.email
        )

    return client

@router.get("/{client_external_id}", response_model=ClientResponse)
def get_client(
    client_external_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    client = ClientService.get_client_by_id(
        db,
        client_external_id=client_external_id,
        user_id=current_user.id
    )
    return client

@router.get("", response_model=list[ClientsByProject])
def list_clients(
    project_external_id: str | None=None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    return ClientService.list_clients(
        db, 
        user_id=current_user.id, 
        project_external_id=project_external_id
    )

@router.patch("/{client_external_id}", response_model=ClientResponse)
def update_client(
    client_external_id: str,
    payload: ClientUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    return ClientService.update_client(
        db = db,
        user_id = current_user.id,
        client_external_id = client_external_id,
        updates = payload.model_dump(exclude_unset=True)
    )

@router.delete("/{client_external_id}")
def delete_client(
    client_external_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    return ClientService.delete_client(
        db = db,
        user_id = current_user.id,
        client_external_id = client_external_id
    )



