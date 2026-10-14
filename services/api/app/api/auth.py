from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.dependencies import get_current_admin
from app.models.workspace import User
from app.schemas.auth import AdminRead, TokenRead
from app.security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    is_valid_jwt_secret,
    verify_password,
)

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])


@router.post("/token", response_model=TokenRead)
def login(
    request: Request,
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: Annotated[Session, Depends(get_session)],
) -> TokenRead:
    secret_key: str | None = request.app.state.jwt_secret_key
    if not is_valid_jwt_secret(secret_key):
        raise HTTPException(status_code=503, detail="JWT_SECRET_KEY is not configured")

    email = form.username.strip().casefold()
    user = session.scalar(select(User).where(User.email == email, User.is_admin.is_(True)))
    if user is None:
        verify_password(form.password, DUMMY_PASSWORD_HASH)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not verify_password(form.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return TokenRead(access_token=create_access_token(user.id, user.workspace_id, secret_key))


@router.get("/me", response_model=AdminRead)
def read_current_admin(current_admin: Annotated[User, Depends(get_current_admin)]) -> User:
    return current_admin
