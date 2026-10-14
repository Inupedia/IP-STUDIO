from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.codex.patches import CanvasPatch
from app.db import get_session
from app.dependencies import get_current_admin
from app.models.codex_patch_proposals import CodexPatchProposal
from app.models.workspace import User
from app.schemas.codex_patches import (
    CodexPatchApprove,
    CodexPatchCreate,
    CodexPatchProposalRead,
    CodexPatchReject,
)
from app.schemas.canvas import CanvasDocument
from app.services.codex_patch_proposal import PatchProposalUnavailable, propose_patch
from app.services.patch_approval import (
    ResourceConflict,
    ResourceNotFound,
    apply_approved_patch,
    create_patch_proposal,
    get_patch_proposal,
    list_patch_proposals,
    reject_patch_proposal,
)

router = APIRouter(prefix="/api/v1", tags=["codex-patches"])


def _read(proposal: CodexPatchProposal) -> CodexPatchProposalRead:
    return CodexPatchProposalRead(
        patch_id=proposal.id,
        approval_id=proposal.approval_id,
        workspace_id=proposal.workspace_id,
        ip_id=proposal.ip_id,
        episode_id=proposal.episode_id,
        document_id=proposal.document_id,
        base_revision=proposal.base_revision,
        patch=CanvasPatch.model_validate(proposal.patch_json),
        preview_document=CanvasDocument.model_validate(proposal.preview_json),
        status=proposal.status,
        created_by_user_id=proposal.created_by_user_id,
        reviewed_by_user_id=proposal.reviewed_by_user_id,
        reviewed_at=proposal.reviewed_at,
        review_note=proposal.review_note,
        applied_revision=proposal.applied_revision,
        created_at=proposal.created_at,
    )


def _raise_resource_error(error: ResourceNotFound | ResourceConflict) -> HTTPException:
    code = status.HTTP_404_NOT_FOUND if isinstance(error, ResourceNotFound) else status.HTTP_409_CONFLICT
    return HTTPException(status_code=code, detail=str(error))


@router.post(
    "/episodes/{episode_id}/codex-patches",
    response_model=CodexPatchProposalRead,
    status_code=status.HTTP_201_CREATED,
)
def create_proposal(
    episode_id: UUID,
    payload: CodexPatchCreate,
    current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> CodexPatchProposalRead:
    try:
        proposal = create_patch_proposal(
            session,
            current_admin.workspace_id,
            current_admin.id,
            episode_id,
            payload.instruction,
            propose_patch,
        )
        return _read(proposal)
    except PatchProposalUnavailable as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
    except (ResourceNotFound, ResourceConflict) as error:
        raise _raise_resource_error(error) from error


@router.get(
    "/episodes/{episode_id}/codex-patches",
    response_model=list[CodexPatchProposalRead],
)
def read_episode_proposals(
    episode_id: UUID,
    current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> list[CodexPatchProposalRead]:
    try:
        return [_read(proposal) for proposal in list_patch_proposals(
            session, current_admin.workspace_id, episode_id
        )]
    except (ResourceNotFound, ResourceConflict) as error:
        raise _raise_resource_error(error) from error


@router.get("/codex/patches/{patch_id}", response_model=CodexPatchProposalRead)
def read_proposal(
    patch_id: UUID,
    current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> CodexPatchProposalRead:
    try:
        return _read(get_patch_proposal(session, current_admin.workspace_id, patch_id))
    except (ResourceNotFound, ResourceConflict) as error:
        raise _raise_resource_error(error) from error


@router.post("/codex/patches/{patch_id}/approve", response_model=CodexPatchProposalRead)
def approve_proposal(
    patch_id: UUID,
    payload: CodexPatchApprove,
    current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> CodexPatchProposalRead:
    try:
        proposal, _document = apply_approved_patch(
            session,
            current_admin.workspace_id,
            current_admin.id,
            patch_id,
            payload.base_revision,
            payload.approval_id,
        )
        return _read(proposal)
    except (ResourceNotFound, ResourceConflict) as error:
        raise _raise_resource_error(error) from error


@router.post("/codex/patches/{patch_id}/reject", response_model=CodexPatchProposalRead)
def reject_proposal(
    patch_id: UUID,
    payload: CodexPatchReject,
    current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> CodexPatchProposalRead:
    try:
        return _read(
            reject_patch_proposal(
                session,
                current_admin.workspace_id,
                current_admin.id,
                patch_id,
                payload.review_note,
            )
        )
    except (ResourceNotFound, ResourceConflict) as error:
        raise _raise_resource_error(error) from error
