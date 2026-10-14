from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import jwt
from pwdlib import PasswordHash

PASSWORD_HASH = PasswordHash.recommended()
DUMMY_PASSWORD_HASH = PASSWORD_HASH.hash("ip-studio-dummy-password")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_MINUTES = 30


def hash_password(password: str) -> str:
    if len(password) < 12:
        raise ValueError("Administrator passwords must contain at least 12 characters")
    return PASSWORD_HASH.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return PASSWORD_HASH.verify(password, password_hash)


def is_valid_jwt_secret(secret_key: str | None) -> bool:
    return bool(secret_key and len(secret_key.encode("utf-8")) >= 32)


def create_access_token(user_id: UUID, workspace_id: UUID, secret_key: str) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_MINUTES)
    return jwt.encode(
        {"sub": str(user_id), "workspace_id": str(workspace_id), "exp": expires_at},
        secret_key,
        algorithm=JWT_ALGORITHM,
    )


def decode_access_token(token: str, secret_key: str) -> dict[str, Any]:
    return jwt.decode(token, secret_key, algorithms=[JWT_ALGORITHM])
