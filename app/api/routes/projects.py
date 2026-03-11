from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.deps import get_current_user

from app.schemas.project import ProjectCreate, ProjectResponse
from app.repositories.project_repository import ProjectRepository


router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectResponse)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    project = ProjectRepository.create(
        db=db,
        user_id=user.id,
        name=payload.name
    )

    return project
