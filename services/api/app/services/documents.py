from copy import deepcopy
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.assets import Asset, AssetVersion
from app.models.bibles import Style, StyleVersion
from app.models.documents import DocumentRevision, EpisodeDocument
from app.models.story import Episode, Series
from app.models.templates import BrandTemplate, BrandTemplateVersion
from app.services.templates import ResourceConflict as TemplateConflict
from app.services.templates import assert_template_shell_unchanged


class ResourceNotFound(Exception):
    pass


class ResourceConflict(Exception):
    pass


def _require_episode(session: Session, workspace_id: UUID, episode_id: UUID) -> tuple[Episode, UUID]:
    row = session.execute(
        select(Episode, Series.ip_id)
        .join(Series, Series.id == Episode.series_id)
        .where(
            Episode.id == episode_id,
            Episode.workspace_id == workspace_id,
            Series.workspace_id == workspace_id,
        )
    ).first()
    if row is None:
        raise ResourceNotFound("Episode not found")
    return row[0], row[1]


def _validate_document_resources(
    session: Session,
    workspace_id: UUID,
    ip_id: UUID,
    document: dict[str, object],
) -> None:
    brand_version_id = UUID(str(document["brand_template_version_id"]))
    brand_row = session.execute(
        select(BrandTemplateVersion, BrandTemplate.ip_id)
        .join(BrandTemplate, BrandTemplate.id == BrandTemplateVersion.brand_template_id)
        .where(
            BrandTemplateVersion.id == brand_version_id,
            BrandTemplateVersion.workspace_id == workspace_id,
            BrandTemplate.workspace_id == workspace_id,
        )
    ).first()
    if brand_row is None or brand_row[1] != ip_id:
        raise ResourceNotFound("Brand template version is not visible in this IP")
    if brand_row[0].status != "approved":
        raise ResourceConflict("Only an approved brand template version can be used by an episode")

    style_version_id_value = document.get("style_version_id")
    if style_version_id_value:
        style_row = session.execute(
            select(StyleVersion, Style.ip_id)
            .join(Style, Style.id == StyleVersion.style_id)
            .where(
                StyleVersion.id == UUID(str(style_version_id_value)),
                StyleVersion.workspace_id == workspace_id,
                Style.workspace_id == workspace_id,
            )
        ).first()
        if style_row is None or style_row[1] != ip_id:
            raise ResourceNotFound("Style version is not visible in this IP")
        if style_row[0].status != "approved":
            raise ResourceConflict("Only an approved style version can be used by an episode")

    asset_version_ids = {
        UUID(str(element["asset_version_id"]))
        for page in document["pages"]  # type: ignore[union-attr]
        for panel in page["panels"]
        for element in panel["elements"]
        if element.get("type") in {"image", "sticker"}
    }
    if not asset_version_ids:
        return
    rows = session.execute(
        select(AssetVersion.id, AssetVersion.status, Asset.owner_ip_id)
        .join(Asset, Asset.id == AssetVersion.asset_id)
        .where(
            AssetVersion.id.in_(asset_version_ids),
            Asset.workspace_id == workspace_id,
        )
    )
    found = {asset_id: (status, owner_ip_id) for asset_id, status, owner_ip_id in rows}
    if set(found) != asset_version_ids or any(owner_ip_id != ip_id for _, owner_ip_id in found.values()):
        raise ResourceNotFound("One or more document assets are not visible in this IP")
    if any(status != "approved" for status, _ in found.values()):
        raise ResourceConflict("Only approved asset versions can be used by an episode")


def get_document(
    session: Session, workspace_id: UUID, episode_id: UUID
) -> tuple[int, dict[str, object] | None]:
    _require_episode(session, workspace_id, episode_id)
    state = session.scalar(
        select(EpisodeDocument).where(
            EpisodeDocument.episode_id == episode_id,
            EpisodeDocument.workspace_id == workspace_id,
        )
    )
    if state is None:
        return 0, None
    return state.current_revision, deepcopy(state.document_json)


def save_document(
    session: Session,
    workspace_id: UUID,
    episode_id: UUID,
    base_revision: int,
    payload: dict[str, object],
    note: str | None = None,
    *,
    commit: bool = True,
) -> tuple[int, dict[str, object]]:
    episode, ip_id = _require_episode(session, workspace_id, episode_id)
    if UUID(str(payload["episode_id"])) != episode.id:
        raise ResourceConflict("Document episode_id does not match the requested episode")
    _validate_document_resources(session, workspace_id, ip_id, payload)
    state = session.scalar(
        select(EpisodeDocument).where(
            EpisodeDocument.episode_id == episode_id,
            EpisodeDocument.workspace_id == workspace_id,
        )
    )
    if state is None:
        if base_revision != 0:
            raise ResourceConflict("Document revision changed; reload the latest version")
        next_revision = 1
    else:
        if state.current_revision != base_revision:
            raise ResourceConflict("Document revision changed; reload the latest version")
        existing_brand_id = str(state.document_json["brand_template_version_id"])
        proposed_brand_id = str(payload["brand_template_version_id"])
        try:
            assert_template_shell_unchanged(
                {"brand_template_version_id": existing_brand_id},
                {"brand_template_version_id": proposed_brand_id},
            )
        except TemplateConflict as error:
            raise ResourceConflict("Changing an episode brand requires an explicit migration") from error
        next_revision = base_revision + 1

    saved_document = deepcopy(payload)
    saved_document["revision"] = next_revision
    now = datetime.now(timezone.utc)
    try:
        if state is None:
            state = EpisodeDocument(
                workspace_id=workspace_id,
                episode_id=episode_id,
                current_revision=next_revision,
                document_json=saved_document,
            )
            session.add(state)
            session.flush()
        else:
            result = session.execute(
                update(EpisodeDocument)
                .where(
                    EpisodeDocument.id == state.id,
                    EpisodeDocument.workspace_id == workspace_id,
                    EpisodeDocument.current_revision == base_revision,
                )
                .values(current_revision=next_revision, document_json=saved_document)
                .execution_options(synchronize_session=False)
            )
            if result.rowcount != 1:
                session.rollback()
                raise ResourceConflict("Document revision changed; reload the latest version")
        session.add(
            DocumentRevision(
                workspace_id=workspace_id,
                episode_id=episode_id,
                revision_no=next_revision,
                snapshot_json=saved_document,
                note=note,
                created_at=now,
            )
        )
        if commit:
            session.commit()
        else:
            session.flush()
    except IntegrityError as error:
        session.rollback()
        raise ResourceConflict("Document revision changed; reload the latest version") from error
    return next_revision, saved_document


def list_document_revisions(
    session: Session, workspace_id: UUID, episode_id: UUID
) -> list[DocumentRevision]:
    _require_episode(session, workspace_id, episode_id)
    return list(
        session.scalars(
            select(DocumentRevision)
            .where(
                DocumentRevision.episode_id == episode_id,
                DocumentRevision.workspace_id == workspace_id,
            )
            .order_by(DocumentRevision.revision_no.desc())
        )
    )


def restore_document_revision(
    session: Session,
    workspace_id: UUID,
    episode_id: UUID,
    revision_no: int,
    base_revision: int,
) -> tuple[int, dict[str, object]]:
    revision = session.scalar(
        select(DocumentRevision).where(
            DocumentRevision.episode_id == episode_id,
            DocumentRevision.workspace_id == workspace_id,
            DocumentRevision.revision_no == revision_no,
        )
    )
    if revision is None:
        raise ResourceNotFound("Document revision not found")
    return save_document(
        session,
        workspace_id,
        episode_id,
        base_revision,
        deepcopy(revision.snapshot_json),
        note=f"Restore revision {revision_no}",
    )
