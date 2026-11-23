"""Manage staff accounts (admin only)."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.services import users as user_service

from .deps import admin_user
from .schemas import UserCreateIn, UserOut

router = APIRouter(prefix="/api/users", tags=["users"], dependencies=[Depends(admin_user)])


@router.get("", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db)):
    return user_service.list_users(db)


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(body: UserCreateIn, db: Session = Depends(get_db)):
    return user_service.create_user(db, body.email, body.name, body.role, body.password)
