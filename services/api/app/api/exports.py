from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db import get_session
from app.dependencies import get_current_admin
from app.models.exports import ExportJob
from app.models.workspace import User
from app.schemas.exports import ExportRead
from app.services.exports import (
    ExportConflict,
    ExportNotFound,
    ExportValidationError,
    create_png_export,
    get_export_file_path,
    get_export_job,
)

router = APIRouter(prefix="/api/v1", tags=["exports"])


def _read(job: ExportJob) -> ExportRead:
    return ExportRead(
        id=job.id,
        episode_id=job.episode_id,
        revision_no=job.revision_no,
        format=job.format,
        status=job.status,
        page_count=job.page_count,
        warnings=job.warnings_json,
        download_url=f"/api/v1/exports/{job.id}/download" if job.file_blob_id else None,
        created_at=job.created_at,
    )


def _raise_export_error(error: ExportNotFound | ExportConflict | ExportValidationError) -> HTTPException:
    if isinstance(error, ExportNotFound):
        code = status.HTTP_404_NOT_FOUND
    elif isinstance(error, ExportValidationError):
        code = error.status_code
    else:
        code = status.HTTP_409_CONFLICT
    return HTTPException(status_code=code, detail=str(error))


@router.post(
    "/episodes/{episode_id}/export",
    response_model=ExportRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_png_export_route(
    episode_id: UUID,
    request: Request,
    current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_session)],
    revision_no: Annotated[int, Form(gt=0)],
    pages: Annotated[list[UploadFile], File()],
) -> ExportRead:
    page_files: list[tuple[bytes, str]] = []
    try:
        for page in pages:
            page_files.append((await page.read(request.app.state.asset_max_bytes + 1), page.content_type or ""))
        try:
            job = create_png_export(
                session,
                current_admin.workspace_id,
                current_admin.id,
                episode_id,
                revision_no,
                page_files,
                Path(request.app.state.asset_storage_dir),
                request.app.state.asset_max_bytes,
                request.app.state.asset_max_pixels,
            )
        except (ExportNotFound, ExportConflict, ExportValidationError) as error:
            raise _raise_export_error(error) from error
        return _read(job)
    finally:
        for page in pages:
            await page.close()


@router.get("/exports/{export_id}", response_model=ExportRead)
def read_export(
    export_id: UUID,
    current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> ExportRead:
    try:
        return _read(get_export_job(session, current_admin.workspace_id, export_id))
    except (ExportNotFound, ExportConflict) as error:
        raise _raise_export_error(error) from error


@router.get("/exports/{export_id}/download")
def download_export(
    export_id: UUID,
    request: Request,
    current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> FileResponse:
    try:
        job, path = get_export_file_path(
            session,
            current_admin.workspace_id,
            export_id,
            Path(request.app.state.asset_storage_dir),
        )
    except (ExportNotFound, ExportConflict) as error:
        raise _raise_export_error(error) from error
    return FileResponse(
        path,
        media_type="application/zip",
        filename=f"episode-r{job.revision_no}-pages.zip",
    )
