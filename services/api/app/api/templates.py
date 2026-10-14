from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_session
from app.dependencies import get_current_admin
from app.models.templates import BrandTemplate, BrandTemplateVersion
from app.models.workspace import User
from app.schemas.templates import (
    BrandTemplateCreate,
    BrandTemplateRead,
    BrandTemplateVersionCandidate,
    BrandTemplateVersionRead,
)
from app.services.templates import (
    ResourceConflict,
    ResourceNotFound,
    approve_brand_version,
    create_brand_candidate,
    create_brand_version_candidate,
    get_brand_version,
    list_brand_templates,
)

router = APIRouter(prefix="/api/v1", tags=["brand-templates"])


def _version_read(version: BrandTemplateVersion) -> BrandTemplateVersionRead:
    return BrandTemplateVersionRead(
        brand_template_version_id=version.id,
        brand_template_id=version.brand_template_id,
        version_no=version.version_no,
        status=version.status,
        template=version.template_json,
        derived_from_version_id=version.derived_from_version_id,
        approved_at=version.approved_at,
    )


def _template_read(
    brand_template: BrandTemplate, versions: list[BrandTemplateVersion]
) -> BrandTemplateRead:
    return BrandTemplateRead(
        brand_template_id=brand_template.id,
        ip_id=brand_template.ip_id,
        name=brand_template.name,
        versions=[_version_read(version) for version in versions],
    )


def _raise_template_error(error: ResourceNotFound | ResourceConflict) -> HTTPException:
    code = status.HTTP_404_NOT_FOUND if isinstance(error, ResourceNotFound) else status.HTTP_409_CONFLICT
    return HTTPException(status_code=code, detail=str(error))


@router.get("/ips/{ip_id}/brand-templates", response_model=list[BrandTemplateRead])
def read_brand_templates(
    ip_id: UUID,
    current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> list[BrandTemplateRead]:
    try:
        return [
            _template_read(template, versions)
            for template, versions in list_brand_templates(session, current_admin.workspace_id, ip_id)
        ]
    except (ResourceNotFound, ResourceConflict) as error:
        raise _raise_template_error(error) from error


@router.post(
    "/ips/{ip_id}/brand-templates",
    response_model=BrandTemplateVersionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_brand_template(
    ip_id: UUID,
    payload: BrandTemplateCreate,
    current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> BrandTemplateVersionRead:
    try:
        _, version = create_brand_candidate(
            session,
            current_admin.workspace_id,
            ip_id,
            payload.name,
            payload.template.model_dump(mode="json"),
        )
        return _version_read(version)
    except (ResourceNotFound, ResourceConflict) as error:
        raise _raise_template_error(error) from error


@router.post(
    "/ips/{ip_id}/brand-templates/{template_id}/versions",
    response_model=BrandTemplateVersionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_brand_version(
    ip_id: UUID,
    template_id: UUID,
    payload: BrandTemplateVersionCandidate,
    current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> BrandTemplateVersionRead:
    try:
        return _version_read(
            create_brand_version_candidate(
                session,
                current_admin.workspace_id,
                ip_id,
                template_id,
                payload.base_version_id,
                payload.template.model_dump(mode="json"),
            )
        )
    except (ResourceNotFound, ResourceConflict) as error:
        raise _raise_template_error(error) from error


@router.get("/brand-template-versions/{version_id}", response_model=BrandTemplateVersionRead)
def read_brand_version(
    version_id: UUID,
    current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> BrandTemplateVersionRead:
    try:
        return _version_read(get_brand_version(session, current_admin.workspace_id, version_id))
    except (ResourceNotFound, ResourceConflict) as error:
        raise _raise_template_error(error) from error


@router.post("/brand-template-versions/{version_id}/approve", response_model=BrandTemplateVersionRead)
def approve_brand_template(
    version_id: UUID,
    current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> BrandTemplateVersionRead:
    try:
        return _version_read(
            approve_brand_version(session, current_admin.workspace_id, version_id, current_admin.id)
        )
    except (ResourceNotFound, ResourceConflict) as error:
        raise _raise_template_error(error) from error
