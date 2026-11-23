"""Staff accounts and login."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.security import hash_password, verify_password
from app.tables import ROLES, User

from .errors import ServiceError, conflict


def normalise_email(email: str) -> str:
    return email.strip().lower()


def authenticate(db: Session, email: str, password: str) -> User:
    user = db.scalar(select(User).where(func.lower(User.email) == normalise_email(email)))
    # Same message for "no such user" and "wrong password": don't reveal which emails exist.
    if user is None or not verify_password(password, user.password_hash):
        raise ServiceError("Wrong email or password.", 401)
    if not user.is_active:
        raise ServiceError("This account has been switched off. Ask an admin.", 403)
    return user


def create_user(db: Session, email: str, name: str, role: str, password: str) -> User:
    if role not in ROLES:
        raise ServiceError(f"Role must be one of: {', '.join(ROLES)}.", 422)
    email = normalise_email(email)
    if db.scalar(select(User).where(User.email == email)):
        raise conflict(f"A user with the email {email} already exists.")
    user = User(email=email, name=name.strip(), role=role, password_hash=hash_password(password))
    db.add(user)
    db.commit()
    return user


def list_users(db: Session) -> list[User]:
    return list(db.scalars(select(User).order_by(User.id)))
