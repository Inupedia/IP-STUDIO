from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models.workspace import User, Workspace
from app.security import hash_password


def normalize_email(email: str) -> str:
    normalized = email.strip().casefold()
    if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
        raise ValueError("Enter a valid administrator email address")
    return normalized


def create_workspace_admin(
    session_factory: sessionmaker[Session], email: str, password: str, workspace_name: str = "IP Studio"
) -> User:
    normalized_email = normalize_email(email)
    password_hash = hash_password(password)

    with session_factory.begin() as session:
        if session.scalar(select(User.id).limit(1)) is not None:
            raise ValueError("An administrator is already configured for this workspace")
        workspace = Workspace(name=workspace_name.strip() or "IP Studio")
        session.add(workspace)
        session.flush()
        user = User(workspace_id=workspace.id, email=normalized_email, password_hash=password_hash)
        session.add(user)
        session.flush()
        session.refresh(user)
        return user
