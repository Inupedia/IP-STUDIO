from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_session
from app.dependencies import get_current_admin
from app.models.workspace import User
from app.schemas.ips import IPCreate, IPRead
from app.services.ips import (
    ResourceConflict,
    ResourceNotFound,
    create_ip,
    get_ip,
    list_ips as list_ip_records,
)

router = APIRouter(prefix="/api/v1/ips", tags=["ips"])


@router.get("", response_model=list[IPRead])
def list_ips(
    current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> list[IPRead]:
    return list_ip_records(session, current_admin.workspace_id)


@router.post("", response_model=IPRead, status_code=status.HTTP_201_CREATED)
def create_ip_route(
    payload: IPCreate,
    current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> IPRead:
    try:
        return create_ip(
            session,
            current_admin.workspace_id,
            payload.code,
            payload.name,
            payload.summary,
        )
    except ResourceConflict as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except ResourceNotFound as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.get("/{ip_id}", response_model=IPRead)
def read_ip(
    ip_id: UUID,
    current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> IPRead:
    try:
        return get_ip(session, current_admin.workspace_id, ip_id)
    except ResourceNotFound as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
