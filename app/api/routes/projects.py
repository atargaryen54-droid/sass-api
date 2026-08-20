from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.deps import get_current_user

from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate
from app.services.project_service import ProjectService



router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectResponse)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    
    project = ProjectService.create_project(
        db,
        name = payload.name, 
        user_id = current_user.id,
        payment_provider = payload.payment_provider,
        billing_frequency = payload.billing_frequency
        )
    
    return project


@router.get("/{project_external_id}", response_model=ProjectResponse)
def get_project(
    project_external_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    project = ProjectService.get_project_by_external_id(
        db, 
        project_external_id=project_external_id, 
        user_id=current_user.id
    )
    
    return project


@router.get("", response_model=list[ProjectResponse])
def list_projects(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    projects = ProjectService.list_projects(
        db,
        user_id=current_user.id
    )
    return projects


@router.patch("/{project_external_id}", response_model=ProjectResponse)
def update_project(
    project_external_id: str,
    payload: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    project = ProjectService.update_project(
        db,
        project_external_id=project_external_id,
        user_id=current_user.id,
        updates=payload.model_dump(exclude_unset=True)
    )
    return project

@router.delete("/{project_external_id}")
def delete_project(
    project_external_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    return(
         ProjectService.delete_project(
                db,
                project_external_id=project_external_id,
                user_id=current_user.id
            )
    )


    
       