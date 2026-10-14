from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_session
from app.dependencies import get_current_admin
from app.models.scripts import ScriptRevision
from app.models.workspace import User
from app.schemas.scripts import (
    MaterializePanelsRequest,
    ScriptMaterializationResult,
    ScriptRevisionCreate,
    ScriptRevisionRead,
    StoryboardPanelRead,
)
from app.services.scripts import (
    DialogueSyncRequired,
    ResourceConflict,
    ResourceNotFound,
    create_script_revision,
    get_script_revision,
    list_script_revisions,
    materialize_panels,
)

router = APIRouter(prefix="/api/v1/episodes", tags=["scripts-and-storyboards"])


def _revision_read(revision: ScriptRevision) -> ScriptRevisionRead:
    return ScriptRevisionRead(
        revision_id=revision.id,
        revision_no=revision.revision_no,
        source_markdown=revision.source_markdown,
        script=revision.script_json,
        note=revision.note,
        created_at=revision.created_at,
    )


def _raise_script_error(error: ResourceNotFound | ResourceConflict) -> HTTPException:
    if isinstance(error, ResourceNotFound):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))
    if isinstance(error, DialogueSyncRequired):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": str(error), "dialogue_changes": error.changes},
        )
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))


@router.get("/{episode_id}/scripts", response_model=list[ScriptRevisionRead])
def read_script_revisions(
    episode_id: UUID,
    current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> list[ScriptRevisionRead]:
    try:
        return [
            _revision_read(revision)
            for revision in list_script_revisions(session, current_admin.workspace_id, episode_id)
        ]
    except (ResourceNotFound, ResourceConflict) as error:
        raise _raise_script_error(error) from error


@router.get("/{episode_id}/scripts/{revision_no}", response_model=ScriptRevisionRead)
def read_script_revision(
    episode_id: UUID,
    revision_no: int,
    current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> ScriptRevisionRead:
    try:
        return _revision_read(
            get_script_revision(session, current_admin.workspace_id, episode_id, revision_no)
        )
    except (ResourceNotFound, ResourceConflict) as error:
        raise _raise_script_error(error) from error


@router.post(
    "/{episode_id}/scripts",
    response_model=ScriptRevisionRead,
    status_code=status.HTTP_201_CREATED,
)
def write_script_revision(
    episode_id: UUID,
    payload: ScriptRevisionCreate,
    current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> ScriptRevisionRead:
    try:
        return _revision_read(
            create_script_revision(
                session,
                current_admin.workspace_id,
                episode_id,
                payload.base_revision,
                payload.script.model_dump(mode="json"),
                payload.source_markdown,
                payload.note,
            )
        )
    except (ResourceNotFound, ResourceConflict) as error:
        raise _raise_script_error(error) from error


@router.post(
    "/{episode_id}/scripts/{revision_no}/materialize",
    response_model=ScriptMaterializationResult,
)
def materialize_script_panels(
    episode_id: UUID,
    revision_no: int,
    payload: MaterializePanelsRequest,
    current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> ScriptMaterializationResult:
    try:
        result = materialize_panels(
            session,
            current_admin.workspace_id,
            episode_id,
            revision_no,
            payload.base_document_revision,
            payload.confirm_dialogue_sync,
        )
        result["panels"] = [StoryboardPanelRead.model_validate(panel) for panel in result["panels"]]
        return ScriptMaterializationResult.model_validate(result)
    except (ResourceNotFound, ResourceConflict) as error:
        raise _raise_script_error(error) from error
