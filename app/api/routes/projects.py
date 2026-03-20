from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.deps import get_current_user

from app.schemas.project import ProjectCreate, ProjectResponse
from app.services.project_service import ProjectService


router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectResponse)
def create(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    project = ProjectService.create_project(db, name = payload.name, user_id = current_user.id)
    
    return project
