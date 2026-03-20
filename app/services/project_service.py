from sqlalchemy.orm import Session
from app.repositories.project_repository import ProjectRepository
from fastapi import HTTPException, status

class ProjectService:

    @staticmethod
    def create_project(db:Session, name, user_id):

        name = name.lower()

        if ProjectRepository.get_by_name_and_user(db, name = name, user_id = user_id ) is not None:
            raise HTTPException(
            status_code=409, 
            detail=f"Service '{name}' already exists for the user."
        )

        project = ProjectRepository.create(
            db=db,
            user_id=user_id,
            name=name
        )
        return project
    
    
