from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path
from typing import Sequence
from uuid import UUID
import zipfile

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.assets import Blob
from app.models.documents import DocumentRevision
from app.models.exports import ExportJob
from app.models.workspace import User
from app.schemas.canvas import CanvasDocument
from app.storage.local_blobs import (
    AssetValidationError,
    inspect_image,
    put_blob,
    resolve_blob_path,
)

MAX_EXPORT_PAGES = 100
MAX_EXPORT_BYTES = 200 * 1024 * 1024


def _file_sha256(path: Path) -> str:
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


class ExportNotFound(Exception):
    pass


class ExportConflict(Exception):
    pass


class ExportValidationError(Exception):
    def __init__(self, message: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.status_code = status_code


def create_png_export(
    session: Session,
    workspace_id: UUID,
    user_id: UUID,
    episode_id: UUID,
    revision_no: int,
    page_files: Sequence[tuple[bytes, str]],
    storage_dir: Path,
    max_page_bytes: int,
    max_pixels: int,
) -> ExportJob:
    if not 1 <= len(page_files) <= MAX_EXPORT_PAGES:
        raise ExportValidationError(f"PNG export must contain between 1 and {MAX_EXPORT_PAGES} pages")

    revision = session.scalar(
        select(DocumentRevision).where(
            DocumentRevision.episode_id == episode_id,
            DocumentRevision.workspace_id == workspace_id,
            DocumentRevision.revision_no == revision_no,
        )
    )
    if revision is None:
        raise ExportNotFound("Document revision not found")
    try:
        document = CanvasDocument.model_validate(revision.snapshot_json)
    except ValidationError as error:
        raise ExportConflict("Stored document revision cannot be rendered") from error
    if document.episode_id != episode_id or document.revision != revision_no:
        raise ExportConflict("Document revision snapshot does not match the requested revision")

    ordered_pages = sorted(document.pages, key=lambda page: page.order)
    if len(ordered_pages) != len(page_files):
        raise ExportValidationError("Uploaded PNG page count does not match the selected revision")

    output = BytesIO()
    total_bytes = 0
    try:
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED, allowZip64=False) as archive:
            for index, (page, (data, declared_mime)) in enumerate(zip(ordered_pages, page_files, strict=True), 1):
                if len(data) > max_page_bytes:
                    raise ExportValidationError("An exported PNG exceeds the per-page size limit", 413)
                total_bytes += len(data)
                if total_bytes > MAX_EXPORT_BYTES:
                    raise ExportValidationError("PNG export exceeds the total size limit", 413)
                try:
                    info = inspect_image(data, declared_mime, max_page_bytes, max_pixels)
                except AssetValidationError as error:
                    raise ExportValidationError(str(error), error.status_code) from error
                if info.mime != "image/png":
                    raise ExportValidationError("PNG export accepts PNG files only", 415)
                if (info.width, info.height) != (page.width, page.height):
                    raise ExportValidationError(
                        f"Page {index} must be rendered at {page.width} × {page.height} px"
                    )
                archive.writestr(f"page-{index:02d}.png", data)
    except zipfile.LargeZipFile as error:
        raise ExportValidationError("PNG export is too large", 413) from error

    archive_data = output.getvalue()
    sha256 = hashlib.sha256(archive_data).hexdigest()
    blob = session.scalar(select(Blob).where(Blob.sha256 == sha256))
    if blob is None:
        storage_key = put_blob(archive_data, sha256, storage_dir)
        blob = Blob(sha256=sha256, storage_key=storage_key, mime="application/zip", byte_size=len(archive_data))
        session.add(blob)
        try:
            session.flush()
        except IntegrityError:
            session.rollback()
            blob = session.scalar(select(Blob).where(Blob.sha256 == sha256))
            if blob is None or blob.mime != "application/zip" or blob.byte_size != len(archive_data):
                raise ExportConflict("Export artifact could not be deduplicated")
            existing_path = resolve_blob_path(storage_dir, blob.storage_key)
            if not existing_path.is_file() or _file_sha256(existing_path) != sha256:
                put_blob(archive_data, sha256, storage_dir)
    elif blob.mime != "application/zip" or blob.byte_size != len(archive_data):
        raise ExportConflict("Stored export blob metadata conflicts with its content hash")
    else:
        blob_path = resolve_blob_path(storage_dir, blob.storage_key)
        if not blob_path.is_file() or _file_sha256(blob_path) != sha256:
            put_blob(archive_data, sha256, storage_dir)

    job = ExportJob(
        workspace_id=workspace_id,
        episode_id=episode_id,
        revision_no=revision_no,
        format="png_zip",
        status="complete",
        file_blob_id=blob.id,
        page_count=len(ordered_pages),
        warnings_json=[],
        created_by_user_id=user_id,
    )
    session.add(job)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise ExportConflict("Export artifact could not be registered") from error
    session.refresh(job)
    return job


def get_export_job(session: Session, workspace_id: UUID, export_id: UUID) -> ExportJob:
    job = session.scalar(
        select(ExportJob).where(
            ExportJob.id == export_id,
            ExportJob.workspace_id == workspace_id,
        )
    )
    if job is None:
        raise ExportNotFound("Export not found")
    return job


def get_export_file_path(
    session: Session,
    workspace_id: UUID,
    export_id: UUID,
    storage_dir: Path,
) -> tuple[ExportJob, Path]:
    row = session.execute(
        select(ExportJob, Blob)
        .join(Blob, Blob.id == ExportJob.file_blob_id)
        .where(ExportJob.id == export_id, ExportJob.workspace_id == workspace_id)
    ).first()
    if row is None:
        raise ExportNotFound("Export not found")
    job, blob = row
    if job.status != "complete":
        raise ExportConflict("Export artifact is not complete")
    path = resolve_blob_path(storage_dir, blob.storage_key)
    if not path.is_file() or path.stat().st_size != blob.byte_size:
        raise ExportNotFound("Export artifact is missing")
    if _file_sha256(path) != blob.sha256:
        raise ExportConflict("Export artifact failed its SHA-256 integrity check")
    return job, path
