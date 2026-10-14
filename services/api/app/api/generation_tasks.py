from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db import get_session
from app.dependencies import get_current_admin
from app.models.generation import GenerationTask
from app.models.workspace import User
from app.schemas.generation import GenerationTaskCreate, GenerationTaskRead
from app.services.generation import (
    ResourceConflict,
    ResourceNotFound,
    create_generation_task,
    get_generation_task,
    start_manual_generation,
)
from app.services.reference_bundle import create_reference_bundle

router = APIRouter(prefix="/api/v1", tags=["generation-tasks"])


def _task_read(task: GenerationTask) -> GenerationTaskRead:
    return GenerationTaskRead(
        task_id=task.id,
        episode_id=task.episode_id,
        script_revision_id=task.script_revision_id,
        script_revision_no=task.script_revision_no,
        panel_id=task.panel_id,
        mode=task.mode,
        status=task.status,
        prompt_snapshot=task.prompt_snapshot,
        reference_snapshot=task.reference_snapshot,
        reference_bundle_url=f"/api/v1/generation-tasks/{task.id}/reference-bundle",
        created_at=task.created_at,
    )


def _raise_generation_error(error: ResourceNotFound | ResourceConflict) -> HTTPException:
    code = (
        status.HTTP_404_NOT_FOUND
        if isinstance(error, ResourceNotFound)
        else status.HTTP_409_CONFLICT
    )
    return HTTPException(status_code=code, detail=str(error))


@router.post(
    "/episodes/{episode_id}/generation-tasks",
    response_model=GenerationTaskRead,
    status_code=status.HTTP_201_CREATED,
)
def create_task(
    episode_id: UUID,
    payload: GenerationTaskCreate,
    current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> GenerationTaskRead:
    try:
        task = create_generation_task(
            session,
            current_admin.workspace_id,
            episode_id,
            payload.script_revision_no,
            payload.panel_id,
            payload.reference_version_ids,
            payload.mode,
        )
        return _task_read(task)
    except (ResourceNotFound, ResourceConflict) as error:
        raise _raise_generation_error(error) from error


@router.get("/generation-tasks/{task_id}", response_model=GenerationTaskRead)
def read_task(
    task_id: UUID,
    current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> GenerationTaskRead:
    try:
        return _task_read(get_generation_task(session, current_admin.workspace_id, task_id))
    except (ResourceNotFound, ResourceConflict) as error:
        raise _raise_generation_error(error) from error


@router.post(
    "/generation-tasks/{task_id}/waiting-manual-generation",
    response_model=GenerationTaskRead,
)
def mark_waiting_manual_generation(
    task_id: UUID,
    current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> GenerationTaskRead:
    try:
        return _task_read(start_manual_generation(session, current_admin.workspace_id, task_id))
    except (ResourceNotFound, ResourceConflict) as error:
        raise _raise_generation_error(error) from error


@router.get("/generation-tasks/{task_id}/reference-bundle")
def read_reference_bundle(
    task_id: UUID,
    request: Request,
    current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    try:
        content = create_reference_bundle(
            session,
            current_admin.workspace_id,
            task_id,
            Path(request.app.state.asset_storage_dir),
        )
        return Response(
            content=content,
            media_type="application/zip",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="generation-task-{task_id}-references.zip"'
                )
            },
        )
    except (ResourceNotFound, ResourceConflict) as error:
        raise _raise_generation_error(error) from error
