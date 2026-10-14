from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.codex.patches import CanvasPatch
from app.models.assets import Asset, AssetVersion
from app.models.codex_patch_proposals import CodexPatchProposal
from app.models.documents import EpisodeDocument
from app.models.story import Episode, Series
from app.services.documents import (
    ResourceConflict as DocumentConflict,
    ResourceNotFound as DocumentNotFound,
    save_document,
)
from app.services.patch_validator import PatchValidationError, Scope, validate_canvas_patch


class ResourceNotFound(Exception):
    pass


class ResourceConflict(Exception):
    pass


PatchGenerator = Callable[..., CanvasPatch]


def _load_scope(
    session: Session, workspace_id: UUID, episode_id: UUID
) -> tuple[Scope, int]:
    row = session.execute(
        select(EpisodeDocument, Series.ip_id)
        .join(Episode, Episode.id == EpisodeDocument.episode_id)
        .join(Series, Series.id == Episode.series_id)
        .where(
            EpisodeDocument.episode_id == episode_id,
            EpisodeDocument.workspace_id == workspace_id,
            Episode.workspace_id == workspace_id,
            Series.workspace_id == workspace_id,
        )
    ).first()
    if row is None:
        episode_exists = session.scalar(
            select(Episode.id).where(Episode.id == episode_id, Episode.workspace_id == workspace_id)
        )
        if episode_exists is None:
            raise ResourceNotFound("Episode not found")
        raise ResourceConflict("Create and save a canvas document before asking Codex for a patch")
    state, ip_id = row
    authorized_assets = frozenset(
        session.scalars(
            select(AssetVersion.id)
            .join(Asset, Asset.id == AssetVersion.asset_id)
            .where(
                AssetVersion.workspace_id == workspace_id,
                AssetVersion.status == "approved",
                Asset.workspace_id == workspace_id,
                Asset.owner_ip_id == ip_id,
                Asset.status == "approved",
            )
        )
    )
    return Scope(
        workspace_id=workspace_id,
        ip_id=ip_id,
        episode_id=episode_id,
        document_id=state.id,
        document=deepcopy(state.document_json),
        authorized_asset_version_ids=authorized_assets,
    ), state.current_revision


def create_patch_proposal(
    session: Session,
    workspace_id: UUID,
    user_id: UUID,
    episode_id: UUID,
    instruction: str,
    generator: PatchGenerator,
) -> CodexPatchProposal:
    normalized_instruction = instruction.strip()
    if not normalized_instruction:
        raise ResourceConflict("Patch instruction cannot be blank")
    initial_scope, base_revision = _load_scope(session, workspace_id, episode_id)
    session.rollback()

    patch = generator(
        instruction=normalized_instruction,
        document=deepcopy(initial_scope.document),
        scope=initial_scope,
        base_revision=base_revision,
    )
    try:
        validate_canvas_patch(patch, initial_scope, base_revision)
    except PatchValidationError as error:
        raise ResourceConflict(str(error)) from error

    current_scope, current_revision = _load_scope(session, workspace_id, episode_id)
    if current_revision != base_revision or current_scope.document_id != initial_scope.document_id:
        session.rollback()
        raise ResourceConflict("Canvas changed while Codex was preparing its patch; retry from the latest revision")
    try:
        validated = validate_canvas_patch(patch, current_scope, current_revision)
    except PatchValidationError as error:
        session.rollback()
        raise ResourceConflict(str(error)) from error

    proposal = CodexPatchProposal(
        workspace_id=workspace_id,
        ip_id=current_scope.ip_id,
        episode_id=episode_id,
        document_id=current_scope.document_id,
        base_revision=current_revision,
        patch_json=validated.patch.model_dump(mode="json"),
        preview_json=validated.document,
        status="pending_approval",
        created_by_user_id=user_id,
    )
    session.add(proposal)
    session.commit()
    session.refresh(proposal)
    return proposal


def get_patch_proposal(
    session: Session, workspace_id: UUID, patch_id: UUID
) -> CodexPatchProposal:
    proposal = session.scalar(
        select(CodexPatchProposal).where(
            CodexPatchProposal.id == patch_id,
            CodexPatchProposal.workspace_id == workspace_id,
        )
    )
    if proposal is None:
        raise ResourceNotFound("Codex patch proposal not found")
    return proposal


def list_patch_proposals(
    session: Session, workspace_id: UUID, episode_id: UUID
) -> list[CodexPatchProposal]:
    if session.scalar(
        select(Episode.id).where(Episode.id == episode_id, Episode.workspace_id == workspace_id)
    ) is None:
        raise ResourceNotFound("Episode not found")
    return list(
        session.scalars(
            select(CodexPatchProposal)
            .where(
                CodexPatchProposal.episode_id == episode_id,
                CodexPatchProposal.workspace_id == workspace_id,
            )
            .order_by(CodexPatchProposal.created_at.desc())
        )
    )


def reject_patch_proposal(
    session: Session,
    workspace_id: UUID,
    user_id: UUID,
    patch_id: UUID,
    review_note: str | None,
) -> CodexPatchProposal:
    proposal = session.scalar(
        select(CodexPatchProposal)
        .where(
            CodexPatchProposal.id == patch_id,
            CodexPatchProposal.workspace_id == workspace_id,
        )
        .with_for_update()
    )
    if proposal is None:
        raise ResourceNotFound("Codex patch proposal not found")
    if proposal.status != "pending_approval":
        raise ResourceConflict("Codex patch proposal has already been reviewed")
    proposal.status = "rejected"
    proposal.reviewed_by_user_id = user_id
    proposal.reviewed_at = datetime.now(timezone.utc)
    proposal.review_note = review_note.strip()[:1000] if review_note and review_note.strip() else None
    session.commit()
    session.refresh(proposal)
    return proposal


def apply_approved_patch(
    session: Session,
    workspace_id: UUID,
    user_id: UUID,
    patch_id: UUID,
    base_revision: int,
    approval_id: UUID,
) -> tuple[CodexPatchProposal, dict[str, Any]]:
    proposal = session.scalar(
        select(CodexPatchProposal)
        .where(
            CodexPatchProposal.id == patch_id,
            CodexPatchProposal.workspace_id == workspace_id,
        )
        .with_for_update()
    )
    if proposal is None:
        raise ResourceNotFound("Codex patch proposal not found")
    if proposal.status != "pending_approval":
        raise ResourceConflict("Codex patch proposal has already been reviewed")
    if proposal.approval_id != approval_id:
        raise ResourceConflict("Patch approval token does not match this proposal")
    if proposal.base_revision != base_revision:
        raise ResourceConflict("Patch base revision does not match the approval request")

    scope, current_revision = _load_scope(session, workspace_id, proposal.episode_id)
    if (
        scope.document_id != proposal.document_id
        or scope.ip_id != proposal.ip_id
        or current_revision != proposal.base_revision
    ):
        session.rollback()
        raise ResourceConflict("Patch base revision is stale; reload and ask Codex for a new proposal")
    try:
        validated = validate_canvas_patch(proposal.patch_json, scope, current_revision)
        next_revision, saved_document = save_document(
            session,
            workspace_id,
            proposal.episode_id,
            base_revision,
            validated.document,
            note=f"Approved Codex patch {proposal.id}",
            commit=False,
        )
    except (PatchValidationError, DocumentConflict, DocumentNotFound) as error:
        session.rollback()
        raise ResourceConflict(str(error)) from error

    proposal.status = "approved"
    proposal.reviewed_by_user_id = user_id
    proposal.reviewed_at = datetime.now(timezone.utc)
    proposal.applied_revision = next_revision
    session.commit()
    session.refresh(proposal)
    return proposal, saved_document
