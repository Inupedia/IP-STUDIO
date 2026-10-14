from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_session
from app.dependencies import get_current_admin
from app.models.documents import DocumentRevision
from app.models.workspace import User
from app.schemas.documents import (
    DocumentRead,
    DocumentRestoreRequest,
    DocumentRevisionRead,
    DocumentRevisionSnapshotRead,
    DocumentSaveRequest,
)
from app.services.documents import (
    ResourceConflict,
    ResourceNotFound,
    get_document,
    list_document_revisions,
    restore_document_revision,
    save_document,
)

router = APIRouter(prefix="/api/v1/episodes", tags=["documents"])


def _raise_document_error(error: ResourceNotFound | ResourceConflict) -> HTTPException:
    code = status.HTTP_404_NOT_FOUND if isinstance(error, ResourceNotFound) else status.HTTP_409_CONFLICT
    return HTTPException(status_code=code, detail=str(error))


def _revision_read(revision: DocumentRevision) -> DocumentRevisionRead:
    return DocumentRevisionRead(
        revision_no=revision.revision_no,
        note=revision.note,
        created_at=revision.created_at,
    )


def _snapshot_read(revision: DocumentRevision) -> DocumentRevisionSnapshotRead:
    return DocumentRevisionSnapshotRead(
        revision_id=revision.id,
        revision_no=revision.revision_no,
        note=revision.note,
        created_at=revision.created_at,
        snapshot=revision.snapshot_json,
    )


@router.get("/{episode_id}/document", response_model=DocumentRead)
def read_document(
    episode_id: UUID,
    current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> DocumentRead:
    try:
        revision, document = get_document(session, current_admin.workspace_id, episode_id)
        return DocumentRead(revision=revision, document=document)
    except (ResourceNotFound, ResourceConflict) as error:
        raise _raise_document_error(error) from error


@router.put("/{episode_id}/document", response_model=DocumentRead)
def write_document(
    episode_id: UUID,
    payload: DocumentSaveRequest,
    current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> DocumentRead:
    try:
        revision, document = save_document(
            session,
            current_admin.workspace_id,
            episode_id,
            payload.base_revision,
            payload.document.model_dump(mode="json"),
            payload.note,
        )
        return DocumentRead(revision=revision, document=document)
    except (ResourceNotFound, ResourceConflict) as error:
        raise _raise_document_error(error) from error


@router.get("/{episode_id}/revisions", response_model=list[DocumentRevisionRead])
def read_revisions(
    episode_id: UUID,
    current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> list[DocumentRevisionRead]:
    try:
        return [_revision_read(revision) for revision in list_document_revisions(
            session, current_admin.workspace_id, episode_id
        )]
    except (ResourceNotFound, ResourceConflict) as error:
        raise _raise_document_error(error) from error


@router.get("/{episode_id}/revisions/{revision_no}", response_model=DocumentRevisionSnapshotRead)
def read_revision(
    episode_id: UUID,
    revision_no: int,
    current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> DocumentRevisionSnapshotRead:
    try:
        revision = next(
            (item for item in list_document_revisions(session, current_admin.workspace_id, episode_id)
             if item.revision_no == revision_no),
            None,
        )
        if revision is None:
            raise HTTPException(status_code=404, detail="Document revision not found")
        return _snapshot_read(revision)
    except (ResourceNotFound, ResourceConflict) as error:
        raise _raise_document_error(error) from error


@router.post("/{episode_id}/restore/{revision_no}", response_model=DocumentRead)
def restore_revision(
    episode_id: UUID,
    revision_no: int,
    payload: DocumentRestoreRequest,
    current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> DocumentRead:
    try:
        revision, document = restore_document_revision(
            session,
            current_admin.workspace_id,
            episode_id,
            revision_no,
            payload.base_revision,
        )
        return DocumentRead(revision=revision, document=document)
    except (ResourceNotFound, ResourceConflict) as error:
        raise _raise_document_error(error) from error
