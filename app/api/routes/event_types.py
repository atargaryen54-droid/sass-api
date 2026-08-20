from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.deps import get_current_user
from app.schemas.event_type import EventTypeCreate, EventTypeResponse, EventTypeUpdate, EventTypesByProject
from app.services.event_type_service import EventTypeService


router = APIRouter(prefix="/event_types", tags=["event_types"])


@router.post("", response_model=EventTypeResponse)
def create_event_type(
    payload: EventTypeCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    event_type = EventTypeService.create_event_type(
        db, 
        project_external_id = payload.project_external_id,
        user_id = current_user.id,
        name = payload.event_name,
        event_code = payload.event_code
        )

    return event_type

@router.get("/{event_type_external_id}", response_model=EventTypeResponse)
def get_event_type(
    event_type_external_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    event_type = EventTypeService.get_event_type_by_id(
        db,
        event_type_external_id=event_type_external_id,
        user_id=current_user.id
    )
    return event_type

@router.get("", response_model=list[EventTypesByProject])
def list_event_types(
    project_external_id: str ,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    return EventTypeService.list_event_types(
        db, 
        user_id=current_user.id, 
        project_external_id=project_external_id
    )

@router.patch("/{event_type_external_id}", response_model=EventTypeResponse)
def update_event_type(
    event_type_external_id: str,
    payload: EventTypeUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    return EventTypeService.update_event_type(
        db = db,
        user_id = current_user.id,
        event_type_external_id = event_type_external_id,
        updates = payload.model_dump(exclude_unset=True)
    )

@router.delete("/{event_type_external_id}")
def delete_event_type(
    event_type_external_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    return EventTypeService.delete_event_type(
        db = db,
        user_id = current_user.id,
        event_type_external_id = event_type_external_id
    )
