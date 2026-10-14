import hashlib
from pathlib import Path
from typing import NamedTuple
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.assets import Asset, AssetLink, AssetVersion, Blob
from app.models.ip import IP
from app.storage.local_blobs import (
    ImageInfo,
    inspect_image,
    put_blob,
    resolve_blob_path,
    storage_key_for_sha256,
)


class ResourceNotFound(Exception):
    pass


class ResourceConflict(Exception):
    pass


class ResourceInUse(Exception):
    pass


class AssetRecord(NamedTuple):
    asset: Asset
    version: AssetVersion
    blob: Blob


def _require_ip(session: Session, workspace_id: UUID, ip_id: UUID) -> None:
    if session.scalar(select(IP.id).where(IP.id == ip_id, IP.workspace_id == workspace_id)) is None:
        raise ResourceNotFound("IP not found")


def _latest_asset_record(
    session: Session,
    workspace_id: UUID,
    ip_id: UUID,
    asset_id: UUID,
    version_id: UUID | None = None,
) -> AssetRecord:
    _require_ip(session, workspace_id, ip_id)
    filters = [
        Asset.id == asset_id,
        Asset.workspace_id == workspace_id,
        Asset.owner_ip_id == ip_id,
    ]
    if version_id is not None:
        filters.append(AssetVersion.id == version_id)
    row = session.execute(
        select(Asset, AssetVersion, Blob)
        .join(AssetVersion, AssetVersion.asset_id == Asset.id)
        .join(Blob, Blob.id == AssetVersion.blob_id)
        .where(*filters)
        .order_by(AssetVersion.version_no.desc())
        .limit(1)
    ).first()
    if row is None:
        raise ResourceNotFound("Asset not found")
    return AssetRecord(*row)


def list_assets(session: Session, workspace_id: UUID, ip_id: UUID) -> list[AssetRecord]:
    _require_ip(session, workspace_id, ip_id)
    rows = session.execute(
        select(Asset, AssetVersion, Blob)
        .join(AssetVersion, AssetVersion.asset_id == Asset.id)
        .join(Blob, Blob.id == AssetVersion.blob_id)
        .where(Asset.workspace_id == workspace_id, Asset.owner_ip_id == ip_id)
        .order_by(Asset.created_at, Asset.id, AssetVersion.version_no.desc())
    )
    latest_by_asset: dict[UUID, AssetRecord] = {}
    for asset, version, blob in rows:
        latest_by_asset.setdefault(asset.id, AssetRecord(asset, version, blob))
    return list(latest_by_asset.values())


def get_asset(
    session: Session, workspace_id: UUID, ip_id: UUID, asset_id: UUID
) -> AssetRecord:
    return _latest_asset_record(session, workspace_id, ip_id, asset_id)


def create_asset_version(
    session: Session,
    workspace_id: UUID,
    asset_id: UUID,
    blob_id: UUID,
    *,
    width: int,
    height: int,
    alpha: bool,
    metadata_json: dict[str, object] | None = None,
) -> AssetVersion:
    asset = session.scalar(
        select(Asset).where(Asset.id == asset_id, Asset.workspace_id == workspace_id)
    )
    blob = session.get(Blob, blob_id)
    if asset is None or blob is None:
        raise ResourceNotFound("Asset or blob not found in this workspace")
    next_version = (session.scalar(
        select(func.max(AssetVersion.version_no)).where(AssetVersion.asset_id == asset_id)
    ) or 0) + 1
    version = AssetVersion(
        workspace_id=workspace_id,
        asset_id=asset_id,
        version_no=next_version,
        blob_id=blob_id,
        width=width,
        height=height,
        alpha=alpha,
        metadata_json=metadata_json or {},
    )
    asset.status = "candidate"
    session.add(version)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise ResourceConflict("Asset version could not be created") from error
    session.refresh(version)
    return version


def _create_asset_records(
    session: Session,
    workspace_id: UUID,
    ip_id: UUID,
    name: str,
    asset_type: str,
    rights_note: str | None,
    original_filename: str,
    info: ImageInfo,
    blob: Blob,
) -> AssetRecord:
    safe_filename = original_filename.replace("\\", "/").rsplit("/", 1)[-1][:200]
    asset = Asset(
        workspace_id=workspace_id,
        owner_ip_id=ip_id,
        type=asset_type,
        name=name.strip(),
        source_type="uploaded",
        rights_note=rights_note.strip() if rights_note and rights_note.strip() else None,
    )
    session.add(asset)
    session.flush()
    version = AssetVersion(
        workspace_id=workspace_id,
        asset_id=asset.id,
        version_no=1,
        blob_id=blob.id,
        width=info.width,
        height=info.height,
        alpha=info.alpha,
        metadata_json={"original_filename": safe_filename},
    )
    session.add(version)
    session.flush()
    return AssetRecord(asset, version, blob)


def _get_or_create_blob(
    session: Session,
    info: ImageInfo,
    data: bytes,
    storage_dir: Path,
) -> Blob:
    blob = session.scalar(select(Blob).where(Blob.sha256 == info.sha256))
    if blob is None:
        storage_key = put_blob(data, info.sha256, storage_dir)
        candidate_blob = Blob(
            sha256=info.sha256,
            storage_key=storage_key,
            mime=info.mime,
            byte_size=info.byte_size,
        )
        session.add(candidate_blob)
        try:
            session.flush()
            blob = candidate_blob
        except IntegrityError:
            session.rollback()
            blob = session.scalar(select(Blob).where(Blob.sha256 == info.sha256))
            if blob is None:
                raise ResourceConflict("Blob could not be registered")

    expected_key = storage_key_for_sha256(info.sha256)
    if blob.storage_key != expected_key or blob.mime != info.mime or blob.byte_size != info.byte_size:
        session.rollback()
        raise ResourceConflict("Stored blob metadata does not match its SHA-256 content address")
    blob_path = resolve_blob_path(storage_dir, blob.storage_key)
    if not blob_path.is_file() or blob_path.stat().st_size != info.byte_size:
        put_blob(data, info.sha256, storage_dir)
    elif hashlib.sha256(blob_path.read_bytes()).hexdigest() != info.sha256:
        put_blob(data, info.sha256, storage_dir)
    return blob


def upload_asset(
    session: Session,
    workspace_id: UUID,
    ip_id: UUID,
    name: str,
    asset_type: str,
    rights_note: str | None,
    original_filename: str,
    data: bytes,
    declared_mime: str,
    storage_dir: Path,
    max_bytes: int,
    max_pixels: int,
) -> AssetRecord:
    _require_ip(session, workspace_id, ip_id)
    normalized_name = name.strip()
    if not normalized_name or len(normalized_name) > 200:
        raise AssetValidationError("Asset name must contain 1 to 200 characters", 422)
    info = inspect_image(data, declared_mime, max_bytes, max_pixels)
    blob = _get_or_create_blob(session, info, data, storage_dir)

    record = _create_asset_records(
        session,
        workspace_id,
        ip_id,
        normalized_name,
        asset_type,
        rights_note,
        original_filename,
        info,
        blob,
    )
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise ResourceConflict("Asset could not be created") from error
    session.refresh(record.asset)
    session.refresh(record.version)
    return record


def add_asset_version_from_upload(
    session: Session,
    workspace_id: UUID,
    ip_id: UUID,
    asset_id: UUID,
    original_filename: str,
    data: bytes,
    declared_mime: str,
    storage_dir: Path,
    max_bytes: int,
    max_pixels: int,
) -> AssetRecord:
    current = _latest_asset_record(session, workspace_id, ip_id, asset_id)
    info = inspect_image(data, declared_mime, max_bytes, max_pixels)
    blob = _get_or_create_blob(session, info, data, storage_dir)
    next_version = (session.scalar(
        select(func.max(AssetVersion.version_no)).where(AssetVersion.asset_id == asset_id)
    ) or 0) + 1
    safe_filename = original_filename.replace("\\", "/").rsplit("/", 1)[-1][:200]
    version = AssetVersion(
        workspace_id=workspace_id,
        asset_id=asset_id,
        version_no=next_version,
        blob_id=blob.id,
        width=info.width,
        height=info.height,
        alpha=info.alpha,
        metadata_json={"original_filename": safe_filename},
    )
    current.asset.status = "candidate"
    session.add(version)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise ResourceConflict("Asset version could not be created") from error
    session.refresh(current.asset)
    session.refresh(version)
    return AssetRecord(current.asset, version, blob)


def get_asset_file_path(
    session: Session,
    workspace_id: UUID,
    ip_id: UUID,
    asset_id: UUID,
    storage_dir: Path,
    version_id: UUID | None = None,
) -> tuple[AssetRecord, Path]:
    record = _latest_asset_record(session, workspace_id, ip_id, asset_id, version_id)
    return record, resolve_blob_path(storage_dir, record.blob.storage_key)


def delete_asset(
    session: Session,
    workspace_id: UUID,
    ip_id: UUID,
    asset_id: UUID,
    storage_dir: Path,
) -> None:
    _require_ip(session, workspace_id, ip_id)
    asset = session.scalar(
        select(Asset).where(
            Asset.id == asset_id,
            Asset.workspace_id == workspace_id,
            Asset.owner_ip_id == ip_id,
        )
    )
    if asset is None:
        raise ResourceNotFound("Asset not found")
    versions = list(session.scalars(select(AssetVersion).where(AssetVersion.asset_id == asset.id)))
    version_ids = [version.id for version in versions]
    if version_ids and session.scalar(
        select(AssetLink.id).where(AssetLink.asset_version_id.in_(version_ids)).limit(1)
    ) is not None:
        raise ResourceInUse("This asset is referenced and cannot be deleted")

    blob_ids = {version.blob_id for version in versions}
    for version in versions:
        session.delete(version)
    session.flush()
    session.delete(asset)
    orphaned_blobs: list[Blob] = []
    for blob_id in blob_ids:
        if session.scalar(select(AssetVersion.id).where(AssetVersion.blob_id == blob_id).limit(1)) is None:
            blob = session.get(Blob, blob_id)
            if blob is not None:
                orphaned_blobs.append(blob)
                session.delete(blob)
    session.commit()

    for blob in orphaned_blobs:
        try:
            resolve_blob_path(storage_dir, blob.storage_key).unlink(missing_ok=True)
        except (OSError, ValueError):
            # The database remains authoritative; an orphaned file can be swept later.
            continue
