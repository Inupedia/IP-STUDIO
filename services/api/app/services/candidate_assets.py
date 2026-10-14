from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.assets import Asset, AssetLink, AssetVersion
from app.models.generation import GenerationTask
from app.models.generation_candidates import GenerationCandidate
from app.models.story import Episode, Series


class ResourceNotFound(Exception):
    pass


class ResourceConflict(Exception):
    pass


def import_candidate(
    session: Session,
    workspace_id: UUID,
    task_id: UUID,
    asset_version_id: UUID,
) -> GenerationCandidate:
    task = session.scalar(
        select(GenerationTask)
        .where(GenerationTask.id == task_id, GenerationTask.workspace_id == workspace_id)
        .with_for_update()
    )
    if task is None:
        raise ResourceNotFound("Generation task not found")
    if task.status not in {"waiting_manual_generation", "asset_imported"}:
        raise ResourceConflict("Start the manual generation task before importing its output")

    ip_id = session.scalar(
        select(Series.ip_id)
        .join(Episode, Episode.series_id == Series.id)
        .where(Episode.id == task.episode_id, Episode.workspace_id == workspace_id)
    )
    if ip_id is None:
        raise ResourceNotFound("Generation task episode not found")

    row = session.execute(
        select(AssetVersion, Asset)
        .join(Asset, Asset.id == AssetVersion.asset_id)
        .where(
            AssetVersion.id == asset_version_id,
            AssetVersion.workspace_id == workspace_id,
            Asset.workspace_id == workspace_id,
        )
    ).first()
    if row is None or row[1].owner_ip_id != ip_id:
        raise ResourceNotFound("Candidate asset version is not visible in this IP")
    version, asset = row
    if version.status != "candidate" or asset.status != "candidate":
        raise ResourceConflict("Only an unapproved candidate asset version can be imported")

    candidate = GenerationCandidate(
        workspace_id=workspace_id,
        task_id=task.id,
        panel_id=task.panel_id,
        asset_version_id=version.id,
        status="pending_review",
    )
    session.add(candidate)
    try:
        session.flush()
        session.add(
            AssetLink(
                asset_version_id=version.id,
                owner_type="generation_candidate",
                owner_id=str(candidate.id),
                role="candidate",
            )
        )
        task.status = "asset_imported"
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise ResourceConflict("This asset version is already bound to a generation candidate") from error
    session.refresh(candidate)
    return candidate
