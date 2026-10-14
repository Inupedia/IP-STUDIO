from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_session
from app.dependencies import get_current_admin
from app.models.generation_candidates import GenerationCandidate
from app.models.workspace import User
from app.schemas.generation_candidates import GenerationCandidateCreate, GenerationCandidateRead
from app.services.candidate_assets import (
    ResourceConflict,
    ResourceNotFound,
    import_candidate,
)

router = APIRouter(prefix="/api/v1/generation-tasks", tags=["generation-candidates"])


def _candidate_read(candidate: GenerationCandidate) -> GenerationCandidateRead:
    return GenerationCandidateRead(
        candidate_id=candidate.id,
        task_id=candidate.task_id,
        panel_id=candidate.panel_id,
        asset_version_id=candidate.asset_version_id,
        status=candidate.status,
        created_at=candidate.created_at,
    )


@router.post(
    "/{task_id}/candidates",
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
        return _candidate_read(
            import_candidate(
                session,
                current_admin.workspace_id,
                task_id,
                payload.asset_version_id,
            )
        )
    except ResourceNotFound as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ResourceConflict as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
