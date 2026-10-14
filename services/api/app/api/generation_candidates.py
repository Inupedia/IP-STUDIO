from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_session
from app.dependencies import get_current_admin
from app.models.workspace import User
from app.schemas.generation_candidates import (
    GenerationCandidateCreate,
    GenerationCandidateRead,
    GenerationCandidateReviewNote,
)
from app.services.candidate_assets import (
    ResourceConflict,
    ResourceNotFound,
    import_candidate,
)
from app.services.candidate_review import (
    CandidateRecord,
    approve_candidate,
    get_candidate_record,
    list_generation_candidates,
    reject_candidate,
)

router = APIRouter(prefix="/api/v1", tags=["generation-candidates"])


def _candidate_read(record: CandidateRecord) -> GenerationCandidateRead:
    candidate = record.candidate
    return GenerationCandidateRead(
        candidate_id=candidate.id,
        task_id=candidate.task_id,
        panel_id=candidate.panel_id,
        asset_id=record.asset.id,
        asset_version_id=record.version.id,
        asset_name=record.asset.name,
        asset_type=record.asset.type,
        version_no=record.version.version_no,
        mime=record.blob.mime,
        sha256=record.blob.sha256,
        byte_size=record.blob.byte_size,
        width=record.version.width,
        height=record.version.height,
        status=candidate.status,
        created_at=candidate.created_at,
        reviewed_at=candidate.reviewed_at,
        reviewed_by_user_id=candidate.reviewed_by_user_id,
        review_note=candidate.review_note,
    )


@router.post(
    "/generation-tasks/{task_id}/candidates",
    response_model=GenerationCandidateRead,
    status_code=status.HTTP_201_CREATED,
)
def import_task_candidate(
    task_id: UUID,
    payload: GenerationCandidateCreate,
    current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> GenerationCandidateRead:
    try:
        candidate = import_candidate(
            session,
            current_admin.workspace_id,
            task_id,
            payload.asset_version_id,
        )
        return _candidate_read(
            get_candidate_record(session, current_admin.workspace_id, candidate.id)
        )
    except ResourceNotFound as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ResourceConflict as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.get("/ips/{ip_id}/generation-candidates", response_model=list[GenerationCandidateRead])
def read_generation_candidates(
    ip_id: UUID,
    current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> list[GenerationCandidateRead]:
    try:
        return [
            _candidate_read(record)
            for record in list_generation_candidates(session, current_admin.workspace_id, ip_id)
        ]
    except ResourceNotFound as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.post(
    "/generation-candidates/{candidate_id}/approve",
    response_model=GenerationCandidateRead,
)
def approve_generation_candidate(
    candidate_id: UUID,
    current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> GenerationCandidateRead:
    try:
        return _candidate_read(
            approve_candidate(
                session,
                current_admin.workspace_id,
                candidate_id,
                current_admin.id,
            )
        )
    except ResourceNotFound as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ResourceConflict as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.post(
    "/generation-candidates/{candidate_id}/reject",
    response_model=GenerationCandidateRead,
)
def reject_generation_candidate(
    candidate_id: UUID,
    payload: GenerationCandidateReviewNote,
    current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> GenerationCandidateRead:
    try:
        return _candidate_read(
            reject_candidate(
                session,
                current_admin.workspace_id,
                candidate_id,
                current_admin.id,
                payload.review_note,
            )
        )
    except ResourceNotFound as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ResourceConflict as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
