import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import UserModel
from app.db.session import get_db
from app.schemas.api import UserRole

settings = get_settings()


@dataclass
class AuthenticatedUser:
    id: str
    full_name: str
    initials: str
    role: str
    email: str


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401)
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401)
    return token


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    return hash_password(password) == password_hash


def create_access_token(user: UserModel) -> tuple[str, int]:
    expires_in = settings.jwt_expires_minutes * 60
    now = datetime.now(UTC)
    payload = {
        "sub": user.id,
        "role": user.role,
        "email": user.email,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_in)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm), expires_in


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401) from exc


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> AuthenticatedUser:
    token = _extract_bearer_token(authorization)
    payload = decode_access_token(token)
    user = db.query(UserModel).filter(UserModel.id == payload.get("sub")).one_or_none()
    if not user:
        raise HTTPException(status_code=401)
    return AuthenticatedUser(
        id=user.id,
        full_name=user.full_name,
        initials=user.initials,
        role=user.role,
        email=user.email,
    )


def require_role(required_role: UserRole):
    def dependency(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
        if user.role != required_role.value:
            raise HTTPException(status_code=403)
        return user

    return dependency
