from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.assets import Asset, AssetVersion
from app.models.ip import IP
from app.models.templates import BrandTemplate, BrandTemplateVersion


class ResourceNotFound(Exception):
    pass


class ResourceConflict(Exception):
    pass


def assert_template_shell_unchanged(
    approved_template: dict[str, object], proposed_template: dict[str, object]
) -> None:
    """Reject ordinary document edits that attempt to change the locked template shell."""
    if approved_template != proposed_template:
        raise ResourceConflict("Episode edits cannot change the locked brand shell")


def _require_ip(session: Session, workspace_id: UUID, ip_id: UUID) -> IP:
    ip = session.scalar(select(IP).where(IP.id == ip_id, IP.workspace_id == workspace_id))
    if ip is None:
        raise ResourceNotFound("IP not found")
    return ip


def _require_template(
    session: Session, workspace_id: UUID, ip_id: UUID, template_id: UUID
) -> BrandTemplate:
    template = session.scalar(
        select(BrandTemplate).where(
            BrandTemplate.id == template_id,
            BrandTemplate.ip_id == ip_id,
            BrandTemplate.workspace_id == workspace_id,
        )
    )
    if template is None:
        raise ResourceNotFound("Brand template not found in this IP")
    return template


def _validate_assets(
    session: Session, workspace_id: UUID, ip_id: UUID, template: dict[str, object]
) -> None:
    elements = template.get("locked_elements", [])
    asset_ids = {
        UUID(str(element["asset_version_id"]))
        for element in elements  # type: ignore[union-attr]
        if isinstance(element, dict) and element.get("asset_version_id")
    }
    if not asset_ids:
        return
    rows = session.execute(
        select(AssetVersion.id, AssetVersion.status, Asset.owner_ip_id)
        .join(Asset, Asset.id == AssetVersion.asset_id)
        .where(AssetVersion.id.in_(asset_ids), Asset.workspace_id == workspace_id)
    )
    found = {asset_id: (asset_status, owner_ip_id) for asset_id, asset_status, owner_ip_id in rows}
    if set(found) != asset_ids or any(owner_ip_id != ip_id for _, owner_ip_id in found.values()):
        raise ResourceNotFound("One or more brand assets are not visible in this IP")
    if any(asset_status != "approved" for asset_status, _ in found.values()):
        raise ResourceConflict("Only approved asset versions can be locked into a brand template")


def create_brand_candidate(
    session: Session,
    workspace_id: UUID,
    ip_id: UUID,
    name: str,
    template: dict[str, object],
) -> tuple[BrandTemplate, BrandTemplateVersion]:
    _require_ip(session, workspace_id, ip_id)
    _validate_assets(session, workspace_id, ip_id, template)
    brand_template = BrandTemplate(workspace_id=workspace_id, ip_id=ip_id, name=name)
    session.add(brand_template)
    try:
        session.flush()
        version = BrandTemplateVersion(
            workspace_id=workspace_id,
            brand_template_id=brand_template.id,
            version_no=1,
            template_json=template,
            status="candidate",
        )
        session.add(version)
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise ResourceConflict("Brand template could not be created") from error
    session.refresh(brand_template)
    session.refresh(version)
    return brand_template, version


def create_brand_version_candidate(
    session: Session,
    workspace_id: UUID,
    ip_id: UUID,
    template_id: UUID,
    base_version_id: UUID,
    template: dict[str, object],
) -> BrandTemplateVersion:
    brand_template = _require_template(session, workspace_id, ip_id, template_id)
    _validate_assets(session, workspace_id, ip_id, template)
    base_version = session.scalar(
        select(BrandTemplateVersion).where(
            BrandTemplateVersion.id == base_version_id,
            BrandTemplateVersion.brand_template_id == brand_template.id,
            BrandTemplateVersion.workspace_id == workspace_id,
        )
    )
    if base_version is None:
        raise ResourceNotFound("Base version does not belong to this IP brand template")
    if base_version.status != "approved":
        raise ResourceConflict("A new brand candidate must derive from an approved version")
    next_version = (
        session.scalar(
            select(func.max(BrandTemplateVersion.version_no)).where(
                BrandTemplateVersion.brand_template_id == brand_template.id
            )
        )
        or 0
    ) + 1
    version = BrandTemplateVersion(
        workspace_id=workspace_id,
        brand_template_id=brand_template.id,
        version_no=next_version,
        template_json=template,
        status="candidate",
        derived_from_version_id=base_version.id,
    )
    session.add(version)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise ResourceConflict("Brand template version could not be created") from error
    session.refresh(version)
    return version


def approve_brand_version(
    session: Session, workspace_id: UUID, version_id: UUID, approver_id: UUID
) -> BrandTemplateVersion:
    version = session.scalar(
        select(BrandTemplateVersion).where(
            BrandTemplateVersion.id == version_id,
            BrandTemplateVersion.workspace_id == workspace_id,
        )
    )
    if version is None:
        raise ResourceNotFound("Brand template version not found")
    if version.status != "candidate":
        raise ResourceConflict("Only a candidate brand version can be approved; approved versions are immutable")
    template = session.get(BrandTemplate, version.brand_template_id)
    if template is None or template.workspace_id != workspace_id:
        raise ResourceNotFound("Brand template not found")
    _validate_assets(session, workspace_id, template.ip_id, version.template_json)
    version.status = "approved"
    version.approved_at = datetime.now(timezone.utc)
    version.approved_by_user_id = approver_id
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise ResourceConflict("Brand template version could not be approved") from error
    session.refresh(version)
    return version


def get_brand_version(
    session: Session, workspace_id: UUID, version_id: UUID
) -> BrandTemplateVersion:
    version = session.scalar(
        select(BrandTemplateVersion).where(
            BrandTemplateVersion.id == version_id,
            BrandTemplateVersion.workspace_id == workspace_id,
        )
    )
    if version is None:
        raise ResourceNotFound("Brand template version not found")
    return version


def list_brand_templates(
    session: Session, workspace_id: UUID, ip_id: UUID
) -> list[tuple[BrandTemplate, list[BrandTemplateVersion]]]:
    _require_ip(session, workspace_id, ip_id)
    templates = list(
        session.scalars(
            select(BrandTemplate)
            .where(BrandTemplate.workspace_id == workspace_id, BrandTemplate.ip_id == ip_id)
            .order_by(BrandTemplate.created_at, BrandTemplate.id)
        )
    )
    return [
        (
            template,
            list(
                session.scalars(
                    select(BrandTemplateVersion)
                    .where(
                        BrandTemplateVersion.workspace_id == workspace_id,
                        BrandTemplateVersion.brand_template_id == template.id,
                    )
                    .order_by(BrandTemplateVersion.version_no)
                )
            ),
        )
        for template in templates
    ]
