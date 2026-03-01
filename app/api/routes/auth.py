from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.schemas.user import UserCreate, UserResponse
from app.services.user_service import UserService
from app.schemas.auth import LoginRequest, TokenResponse
from app.services.auth_service import AuthService
from fastapi import Body

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", response_model=UserResponse)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    user = UserService.register_user(db, user_in.email, user_in.password)
    return user

@router.post("/login", response_model=TokenResponse)
def login(login_in: LoginRequest, db: Session = Depends(get_db)):
    tokens = AuthService.login(db, login_in.email, login_in.password)
    return tokens


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    refresh_token: str = Body(...),
    db: Session = Depends(get_db)
):
    return AuthService.refresh(db, refresh_token)