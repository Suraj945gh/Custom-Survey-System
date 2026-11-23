"""Log in, and see who you are."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.security import make_token
from app.services import users as user_service
from app.tables import User

from .deps import current_user
from .schemas import LoginIn, LoginOut, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=LoginOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = user_service.authenticate(db, body.email, body.password)
    return LoginOut(token=make_token(user.id), user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user
