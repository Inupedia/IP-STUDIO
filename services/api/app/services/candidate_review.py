from datetime import datetime, timezone
from typing import NamedTuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.assets import Asset, AssetVersion, Blob
from app.models.generation import GenerationTask
from app.models.generation_candidates import GenerationCandidate
from app.models.ip import IP
from app.models.story import Episode, Series
from app.services.candidate_assets import ResourceConflict, ResourceNotFound


class CandidateRecord(NamedTuple):
    candidate: GenerationCandidate
    version: AssetVersion
    asset: Asset
    blob: Blob


def _candidate_record_query():
    return (
        select(GenerationCandidate, AssetVersion, Asset, Blob)
        .join(AssetVersion, AssetVersion.id == GenerationCandidate.asset_version_id)
        .join(Asset, Asset.id == AssetVersion.asset_id)
        .join(Blob, Blob.id == AssetVersion.blob_id)
    )


def _get_candidate_record(
    session: Session, workspace_id: UUID, candidate_id: UUID, *, lock: bool = False
) -> CandidateRecord:
    query = _candidate_record_query().where(
        GenerationCandidate.id == candidate_id,
        GenerationCandidate.workspace_id == workspace_id,
    )
    if lock:
        query = query.with_for_update()
    row = session.execute(query).first()
    if row is None:
        raise ResourceNotFound("Generation candidate not found")
    return CandidateRecord(*row)


def get_candidate_record(
    session: Session, workspace_id: UUID, candidate_id: UUID
) -> CandidateRecord:
    return _get_candidate_record(session, workspace_id, candidate_id)


def list_generation_candidates(
    session: Session, workspace_id: UUID, ip_id: UUID
) -> list[CandidateRecord]:
    if session.scalar(select(IP.id).where(IP.id == ip_id, IP.workspace_id == workspace_id)) is None:
        raise ResourceNotFound("IP not found")
    rows = session.execute(
        _candidate_record_query()
        .join(GenerationTask, GenerationTask.id == GenerationCandidate.task_id)
        .join(Episode, Episode.id == GenerationTask.episode_id)
        .join(Series, Series.id == Episode.series_id)
        .where(
            GenerationCandidate.workspace_id == workspace_id,
            Episode.workspace_id == workspace_id,
            Series.workspace_id == workspace_id,
            Series.ip_id == ip_id,
        )
        .order_by(GenerationCandidate.created_at.desc(), GenerationCandidate.id)
    )
    return [CandidateRecord(*row) for row in rows]


def approve_candidate(
    session: Session,
    workspace_id: UUID,
    candidate_id: UUID,
    reviewer_id: UUID,
) -> CandidateRecord:
    record = _get_candidate_record(session, workspace_id, candidate_id, lock=True)
    if record.candidate.status != "pending_review":
        raise ResourceConflict("Only a pending candidate can be approved")
    if record.version.status != "candidate":
        raise ResourceConflict("Candidate asset version is no longer awaiting approval")

    reviewed_at = datetime.now(timezone.utc)
    record.candidate.status = "approved"
    record.candidate.reviewed_at = reviewed_at
    record.candidate.reviewed_by_user_id = reviewer_id
    record.candidate.review_note = None
    record.version.status = "approved"
    record.version.approved_at = reviewed_at
    record.version.approved_by_user_id = reviewer_id
    latest_version_id = session.scalar(
        select(AssetVersion.id)
        .where(AssetVersion.asset_id == record.asset.id)
        .order_by(AssetVersion.version_no.desc())
        .limit(1)
    )
    if latest_version_id == record.version.id:
        record.asset.status = "approved"
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise ResourceConflict("Candidate approval could not be recorded") from error
    return _get_candidate_record(session, workspace_id, candidate_id)


def reject_candidate(
    session: Session,
    workspace_id: UUID,
    candidate_id: UUID,
    reviewer_id: UUID,
    review_note: str | None = None,
) -> CandidateRecord:
    record = _get_candidate_record(session, workspace_id, candidate_id, lock=True)
    if record.candidate.status != "pending_review":
        raise ResourceConflict("Only a pending candidate can be rejected")
    if record.version.status != "candidate":
        raise ResourceConflict("Candidate asset version is no longer awaiting review")

    reviewed_at = datetime.now(timezone.utc)
    record.candidate.status = "rejected"
    record.candidate.reviewed_at = reviewed_at
    record.candidate.reviewed_by_user_id = reviewer_id
    record.candidate.review_note = review_note.strip() if review_note and review_note.strip() else None
    record.version.status = "archived"
    latest_version_id = session.scalar(
        select(AssetVersion.id)
        .where(AssetVersion.asset_id == record.asset.id)
        .order_by(AssetVersion.version_no.desc())
        .limit(1)
    )
    if latest_version_id == record.version.id:
        record.asset.status = "archived"
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise ResourceConflict("Candidate rejection could not be recorded") from error
    return _get_candidate_record(session, workspace_id, candidate_id)
