from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db import get_session
from app.dependencies import get_current_admin
from app.models.workspace import User
from app.schemas.assets import AssetType, AssetUploadRead
from app.services.assets import (
    AssetRecord,
    ResourceConflict,
    ResourceInUse,
    ResourceNotFound,
    add_asset_version_from_upload,
    delete_asset,
    get_asset,
    get_asset_file_path,
    get_asset_version,
    list_assets,
    upload_asset,
)
from app.services.bibles import (
    ResourceConflict as BibleConflict,
    ResourceNotFound as BibleNotFound,
    approve_asset_version,
)
from app.storage.local_blobs import AssetValidationError

router = APIRouter(prefix="/api/v1/assets", tags=["assets"])


def _to_read(record: AssetRecord) -> AssetUploadRead:
    return AssetUploadRead(
        asset_id=record.asset.id,
        asset_version_id=record.version.id,
        workspace_id=record.asset.workspace_id,
        owner_ip_id=record.asset.owner_ip_id,
        type=record.asset.type,
        name=record.asset.name,
        status=record.version.status,
        source_type=record.asset.source_type,
        version_no=record.version.version_no,
        sha256=record.blob.sha256,
        mime=record.blob.mime,
        byte_size=record.blob.byte_size,
        width=record.version.width,
        height=record.version.height,
        alpha=record.version.alpha,
        created_at=record.version.created_at,
    )


@router.get("", response_model=list[AssetUploadRead])
def read_assets(
    current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_session)],
    ip_id: UUID,
) -> list[AssetUploadRead]:
    try:
        return [_to_read(record) for record in list_assets(session, current_admin.workspace_id, ip_id)]
    except ResourceNotFound as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.get("/versions/{version_id}", response_model=AssetUploadRead)
def read_asset_version(
    version_id: UUID,
    current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_session)],
    ip_id: UUID,
) -> AssetUploadRead:
    try:
        return _to_read(get_asset_version(session, current_admin.workspace_id, ip_id, version_id))
    except ResourceNotFound as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.post("/upload", response_model=AssetUploadRead, status_code=status.HTTP_201_CREATED)
async def upload_asset_route(
    request: Request,
    current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_session)],
    ip_id: Annotated[UUID, Form()],
    name: Annotated[str, Form(min_length=1, max_length=200)],
    asset_type: Annotated[AssetType, Form(alias="type")],
    file: Annotated[UploadFile, File()],
    rights_note: Annotated[str | None, Form(max_length=4000)] = None,
) -> AssetUploadRead:
    max_bytes: int = request.app.state.asset_max_bytes
    try:
        data = await file.read(max_bytes + 1)
        try:
            record = upload_asset(
                session,
                current_admin.workspace_id,
                ip_id,
                name,
                asset_type.value,
                rights_note,
                file.filename or "upload",
                data,
                file.content_type or "",
                request.app.state.asset_storage_dir,
                max_bytes,
                request.app.state.asset_max_pixels,
            )
        except AssetValidationError as error:
            raise HTTPException(status_code=error.status_code, detail=str(error)) from error
        except ResourceNotFound as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
        except ResourceConflict as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
        return _to_read(record)
    finally:
        await file.close()


@router.post(
    "/{asset_id}/versions",
    response_model=AssetUploadRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_asset_version(
    asset_id: UUID,
    request: Request,
    current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_session)],
    ip_id: Annotated[UUID, Form()],
    file: Annotated[UploadFile, File()],
) -> AssetUploadRead:
    max_bytes: int = request.app.state.asset_max_bytes
    try:
        data = await file.read(max_bytes + 1)
        try:
            record = add_asset_version_from_upload(
                session,
                current_admin.workspace_id,
                ip_id,
                asset_id,
                file.filename or "upload",
                data,
                file.content_type or "",
                request.app.state.asset_storage_dir,
                max_bytes,
                request.app.state.asset_max_pixels,
            )
        except AssetValidationError as error:
            raise HTTPException(status_code=error.status_code, detail=str(error)) from error
        except ResourceNotFound as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
        except ResourceConflict as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
        return _to_read(record)
    finally:
        await file.close()


@router.get("/{asset_id}", response_model=AssetUploadRead)
def read_asset(
    asset_id: UUID,
    current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_session)],
    ip_id: UUID,
) -> AssetUploadRead:
    try:
        return _to_read(get_asset(session, current_admin.workspace_id, ip_id, asset_id))
    except ResourceNotFound as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.post(
    "/{asset_id}/versions/{version_id}/approve", response_model=AssetUploadRead
)
def approve_asset_version_route(
    asset_id: UUID,
    version_id: UUID,
    request: Request,
    current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_session)],
    ip_id: UUID,
) -> AssetUploadRead:
    try:
        approve_asset_version(
            session,
            current_admin.workspace_id,
            ip_id,
            asset_id,
            version_id,
            current_admin.id,
        )
        record, _ = get_asset_file_path(
            session,
            current_admin.workspace_id,
            ip_id,
            asset_id,
            Path(request.app.state.asset_storage_dir),
            version_id,
        )
        return _to_read(record)
    except (BibleNotFound, ResourceNotFound) as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except (BibleConflict, ResourceConflict) as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.get("/{asset_id}/content")
def read_asset_content(
    asset_id: UUID,
    request: Request,
    current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_session)],
    ip_id: UUID,
    version_id: UUID | None = Query(default=None),
) -> FileResponse:
    try:
        record, path = get_asset_file_path(
            session,
            current_admin.workspace_id,
            ip_id,
            asset_id,
            Path(request.app.state.asset_storage_dir),
            version_id,
        )
    except ResourceNotFound as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset content is missing")
    return FileResponse(path, media_type=record.blob.mime)


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_asset(
    asset_id: UUID,
    request: Request,
    current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_session)],
    ip_id: UUID,
    confirm: Annotated[bool, Query()] = False,
) -> None:
    if not confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Explicit confirmation is required to delete an asset",
        )
    try:
        delete_asset(
            session,
            current_admin.workspace_id,
            ip_id,
            asset_id,
            Path(request.app.state.asset_storage_dir),
        )
    except ResourceNotFound as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ResourceInUse as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
