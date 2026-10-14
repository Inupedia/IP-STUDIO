from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models.workspace import User
from app.security import decode_access_token, is_valid_jwt_secret

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


def get_current_admin(
    request: Request,
    token: Annotated[str, Depends(oauth2_scheme)],
    session: Annotated[Session, Depends(get_session)],
) -> User:
    secret_key: str | None = request.app.state.jwt_secret_key
    if not is_valid_jwt_secret(secret_key):
        raise HTTPException(status_code=503, detail="JWT_SECRET_KEY is not configured")

    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        claims = decode_access_token(token, secret_key)
        user_id = UUID(claims["sub"])
        workspace_id = UUID(claims["workspace_id"])
    except (KeyError, TypeError, ValueError, jwt.InvalidTokenError) as error:
        raise credentials_error from error

    user = session.scalar(
        select(User).where(
            User.id == user_id,
            User.workspace_id == workspace_id,
            User.is_admin.is_(True),
        )
    )
    if user is None:
        raise credentials_error
    return user
