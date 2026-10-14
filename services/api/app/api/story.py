from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_session
from app.dependencies import get_current_admin
from app.models.workspace import User
from app.schemas.ips import EpisodeCreate, EpisodeRead, SeriesCreate, SeriesRead
from app.services.ips import (
    ResourceConflict,
    ResourceNotFound,
    create_episode,
    create_series,
    list_episodes,
    list_series,
)

router = APIRouter(prefix="/api/v1/series", tags=["story"])


@router.get("", response_model=list[SeriesRead])
def read_series(
    current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_session)],
    ip_id: UUID | None = None,
) -> list[SeriesRead]:
    try:
        return list_series(session, current_admin.workspace_id, ip_id)
    except ResourceNotFound as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.post("", response_model=SeriesRead, status_code=status.HTTP_201_CREATED)
def create_series_route(
    payload: SeriesCreate,
    current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> SeriesRead:
    try:
        return create_series(
            session,
            current_admin.workspace_id,
            payload.ip_id,
            payload.name,
            payload.summary,
        )
    except ResourceNotFound as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ResourceConflict as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.get("/{series_id}/episodes", response_model=list[EpisodeRead])
def read_episodes(
    series_id: UUID,
    current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> list[EpisodeRead]:
    try:
        return list_episodes(session, current_admin.workspace_id, series_id)
    except ResourceNotFound as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.post(
    "/{series_id}/episodes",
    response_model=EpisodeRead,
    status_code=status.HTTP_201_CREATED,
)
def create_episode_route(
    series_id: UUID,
    payload: EpisodeCreate,
    current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> EpisodeRead:
    try:
        return create_episode(
            session,
            current_admin.workspace_id,
            series_id,
            payload.number,
            payload.title,
        )
    except ResourceNotFound as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ResourceConflict as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
