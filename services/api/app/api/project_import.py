from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db import get_session
from app.dependencies import get_current_admin
from app.export.project_bundle import (
    MAX_BUNDLE_UPLOAD_BYTES,
    ProjectBundleConflict,
    ProjectBundleNotFound,
    ProjectBundleValidationError,
    export_project_bundle,
    import_project_bundle,
)
from app.models.workspace import User
from app.schemas.project_bundle import ProjectBundleExportRequest, ProjectBundleImportRead

router = APIRouter(prefix="/api/v1", tags=["portable-projects"])


def _raise_bundle_error(
    error: ProjectBundleNotFound | ProjectBundleConflict | ProjectBundleValidationError,
) -> HTTPException:
    if isinstance(error, ProjectBundleNotFound):
        code = status.HTTP_404_NOT_FOUND
    elif isinstance(error, ProjectBundleValidationError):
        code = error.status_code
    else:
        code = status.HTTP_409_CONFLICT
    return HTTPException(status_code=code, detail=str(error))


@router.post("/episodes/{episode_id}/project-bundle")
def export_project_bundle_route(
    episode_id: UUID,
    payload: ProjectBundleExportRequest,
    request: Request,
    current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    try:
        bundle = export_project_bundle(
            session,
            current_admin.workspace_id,
            episode_id,
            payload.revision_no,
            Path(request.app.state.asset_storage_dir),
            request.app.state.asset_max_bytes,
            request.app.state.asset_max_pixels,
        )
    except (ProjectBundleNotFound, ProjectBundleConflict, ProjectBundleValidationError) as error:
        raise _raise_bundle_error(error) from error
    return Response(
        content=bundle,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="episode-{episode_id}-project.zip"'},
    )


@router.post(
    "/projects/import",
    response_model=ProjectBundleImportRead,
    status_code=status.HTTP_201_CREATED,
)
async def import_project_bundle_route(
    request: Request,
    current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_session)],
    ip_id: Annotated[UUID, Form()],
    file: Annotated[UploadFile, File()],
) -> ProjectBundleImportRead:
    try:
        payload = await file.read(MAX_BUNDLE_UPLOAD_BYTES + 1)
        if len(payload) > MAX_BUNDLE_UPLOAD_BYTES:
            raise ProjectBundleValidationError("Project bundle exceeds the upload limit", 413)
        imported = import_project_bundle(
            session,
            current_admin.workspace_id,
            current_admin.id,
            ip_id,
            payload,
            Path(request.app.state.asset_storage_dir),
            request.app.state.asset_max_bytes,
            request.app.state.asset_max_pixels,
        )
        return ProjectBundleImportRead.model_validate(imported)
    except (ProjectBundleNotFound, ProjectBundleConflict, ProjectBundleValidationError) as error:
        raise _raise_bundle_error(error) from error
    finally:
        await file.close()
