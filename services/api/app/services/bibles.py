from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.assets import Asset, AssetLink, AssetVersion
from app.models.bibles import Character, CharacterVersion, Style, StyleVersion
from app.models.ip import IP

class ResourceNotFound(Exception):
    pass


class ResourceConflict(Exception):
    pass


def _require_ip(session: Session, workspace_id: UUID, ip_id: UUID) -> IP:
    ip = session.scalar(select(IP).where(IP.id == ip_id, IP.workspace_id == workspace_id))
    if ip is None:
        raise ResourceNotFound("IP not found")
    return ip


def _validate_asset_references(
    session: Session, workspace_id: UUID, ip_id: UUID, bible: dict[str, object]
) -> None:
    reference_keys = (
        "standard_reference_asset_version_ids",
        "expression_asset_version_ids",
        "pose_asset_version_ids",
        "costume_asset_version_ids",
        "example_asset_version_ids",
    )
    reference_ids = {
        UUID(str(reference_id))
        for key in reference_keys
        for reference_id in bible.get(key, [])  # type: ignore[union-attr]
    }
    if not reference_ids:
        return

    rows = session.execute(
        select(AssetVersion.id, AssetVersion.status, Asset.owner_ip_id)
        .join(Asset, Asset.id == AssetVersion.asset_id)
        .where(
            AssetVersion.id.in_(reference_ids),
            Asset.workspace_id == workspace_id,
        )
    )
    found = {asset_version_id: (status, owner_ip_id) for asset_version_id, status, owner_ip_id in rows}
    if set(found) != reference_ids or any(owner_ip_id != ip_id for _, owner_ip_id in found.values()):
        raise ResourceNotFound("One or more reference assets are not visible in this IP")
    if any(asset_status != "approved" for asset_status, _ in found.values()):
        raise ResourceConflict("Only approved asset versions can be referenced by a Bible")


def _create_candidate(
    session: Session,
    model: type[Character] | type[Style],
    version_model: type[CharacterVersion] | type[StyleVersion],
    workspace_id: UUID,
    ip_id: UUID,
    name: str,
    bible: dict[str, object],
    code: str | None = None,
) -> tuple[Character | Style, CharacterVersion | StyleVersion]:
    _require_ip(session, workspace_id, ip_id)
    _validate_asset_references(session, workspace_id, ip_id, bible)
    fields: dict[str, object] = {
        "workspace_id": workspace_id,
        "ip_id": ip_id,
        "name": name,
    }
    if code is not None:
        fields["code"] = code
    entity = model(**fields)
    session.add(entity)
    entity_key = "character_id" if isinstance(entity, Character) else "style_id"
    try:
        session.flush()
        version = version_model(
            workspace_id=workspace_id,
            **{entity_key: entity.id},
            version_no=1,
            bible_json=bible,
            status="candidate",
        )
        session.add(version)
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise ResourceConflict("The Bible record could not be created; its code or version may already exist") from error
    session.refresh(entity)
    session.refresh(version)
    return entity, version


def create_character_candidate(
    session: Session,
    workspace_id: UUID,
    ip_id: UUID,
    code: str,
    name: str,
    bible: dict[str, object],
) -> tuple[Character, CharacterVersion]:
    entity, version = _create_candidate(
        session, Character, CharacterVersion, workspace_id, ip_id, name, bible, code
    )
    assert isinstance(entity, Character) and isinstance(version, CharacterVersion)
    return entity, version


def create_style_candidate(
    session: Session,
    workspace_id: UUID,
    ip_id: UUID,
    name: str,
    bible: dict[str, object],
) -> tuple[Style, StyleVersion]:
    entity, version = _create_candidate(
        session, Style, StyleVersion, workspace_id, ip_id, name, bible
    )
    assert isinstance(entity, Style) and isinstance(version, StyleVersion)
    return entity, version


def _create_derived_candidate(
    session: Session,
    workspace_id: UUID,
    entity_id: UUID,
    base_version_id: UUID | None,
    bible: dict[str, object],
    entity_model: type[Character] | type[Style],
    version_model: type[CharacterVersion] | type[StyleVersion],
    entity_key: str,
) -> CharacterVersion | StyleVersion:
    entity = session.scalar(
        select(entity_model).where(entity_model.id == entity_id, entity_model.workspace_id == workspace_id)
    )
    if entity is None:
        raise ResourceNotFound("Bible entity not found")
    _validate_asset_references(session, workspace_id, entity.ip_id, bible)

    base_version: CharacterVersion | StyleVersion | None = None
    if base_version_id is not None:
        base_version = session.scalar(
            select(version_model).where(
                version_model.id == base_version_id,
                getattr(version_model, entity_key) == entity_id,
                version_model.workspace_id == workspace_id,
            )
        )
        if base_version is None:
            raise ResourceNotFound("Base version does not belong to this Bible entity")
        if base_version.status != "approved":
            raise ResourceConflict("A new candidate must derive from an approved version")

    next_version = (session.scalar(
        select(func.max(version_model.version_no)).where(getattr(version_model, entity_key) == entity_id)
    ) or 0) + 1
    version_fields: dict[str, object] = {
        "workspace_id": workspace_id,
        entity_key: entity_id,
        "version_no": next_version,
        "bible_json": bible,
        "status": "candidate",
        "derived_from_version_id": base_version_id,
    }
    version = version_model(**version_fields)
    session.add(version)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise ResourceConflict("Bible candidate could not be created") from error
    session.refresh(version)
    return version


def create_character_version_candidate(
    session: Session,
    workspace_id: UUID,
    character_id: UUID,
    base_version_id: UUID | None,
    bible: dict[str, object],
) -> CharacterVersion:
    result = _create_derived_candidate(
        session,
        workspace_id,
        character_id,
        base_version_id,
        bible,
        Character,
        CharacterVersion,
        "character_id",
    )
    assert isinstance(result, CharacterVersion)
    return result


def create_style_version_candidate(
    session: Session,
    workspace_id: UUID,
    style_id: UUID,
    base_version_id: UUID | None,
    bible: dict[str, object],
) -> StyleVersion:
    result = _create_derived_candidate(
        session,
        workspace_id,
        style_id,
        base_version_id,
        bible,
        Style,
        StyleVersion,
        "style_id",
    )
    assert isinstance(result, StyleVersion)
    return result


def _approve_version(
    session: Session,
    version_model: type[CharacterVersion] | type[StyleVersion],
    workspace_id: UUID,
    version_id: UUID,
    approver_id: UUID,
) -> CharacterVersion | StyleVersion:
    version = session.scalar(
        select(version_model).where(
            version_model.id == version_id,
            version_model.workspace_id == workspace_id,
        )
    )
    if version is None:
        raise ResourceNotFound("Bible version not found")
    if version.status != "candidate":
        raise ResourceConflict("Only a candidate version can be approved; approved versions are immutable")
    _validate_asset_references(session, workspace_id, _get_version_ip_id(session, version), version.bible_json)
    version.status = "approved"
    version.approved_at = datetime.now(timezone.utc)
    version.approved_by_user_id = approver_id
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise ResourceConflict("Bible version could not be approved") from error
    session.refresh(version)
    return version


def _get_version_ip_id(
    session: Session, version: CharacterVersion | StyleVersion
) -> UUID:
    if isinstance(version, CharacterVersion):
        entity = session.get(Character, version.character_id)
    else:
        entity = session.get(Style, version.style_id)
    if entity is None:
        raise ResourceNotFound("Bible entity not found")
    return entity.ip_id


def approve_character_version(
    session: Session, workspace_id: UUID, version_id: UUID, approver_id: UUID
) -> CharacterVersion:
    version = _approve_version(
        session, CharacterVersion, workspace_id, version_id, approver_id
    )
    assert isinstance(version, CharacterVersion)
    return version


def approve_style_version(
    session: Session, workspace_id: UUID, version_id: UUID, approver_id: UUID
) -> StyleVersion:
    version = _approve_version(session, StyleVersion, workspace_id, version_id, approver_id)
    assert isinstance(version, StyleVersion)
    return version


def _list_entities_with_versions(
    session: Session,
    workspace_id: UUID,
    ip_id: UUID,
    entity_model: type[Character] | type[Style],
    version_model: type[CharacterVersion] | type[StyleVersion],
    entity_key: str,
) -> list[tuple[Character | Style, list[CharacterVersion | StyleVersion]]]:
    _require_ip(session, workspace_id, ip_id)
    entities = list(
        session.scalars(
            select(entity_model)
            .where(entity_model.workspace_id == workspace_id, entity_model.ip_id == ip_id)
            .order_by(entity_model.created_at, entity_model.id)
        )
    )
    result: list[tuple[Character | Style, list[CharacterVersion | StyleVersion]]] = []
    for entity in entities:
        versions = list(
            session.scalars(
                select(version_model)
                .where(getattr(version_model, entity_key) == entity.id)
                .order_by(version_model.version_no.desc())
            )
        )
        result.append((entity, versions))
    return result


def list_characters(
    session: Session, workspace_id: UUID, ip_id: UUID
) -> list[tuple[Character, list[CharacterVersion]]]:
    result = _list_entities_with_versions(
        session, workspace_id, ip_id, Character, CharacterVersion, "character_id"
    )
    return [(entity, versions) for entity, versions in result if isinstance(entity, Character)]  # type: ignore[list-item]


def list_styles(
    session: Session, workspace_id: UUID, ip_id: UUID
) -> list[tuple[Style, list[StyleVersion]]]:
    result = _list_entities_with_versions(
        session, workspace_id, ip_id, Style, StyleVersion, "style_id"
    )
    return [(entity, versions) for entity, versions in result if isinstance(entity, Style)]  # type: ignore[list-item]


def get_character_version(
    session: Session, workspace_id: UUID, version_id: UUID
) -> CharacterVersion:
    version = session.scalar(
        select(CharacterVersion).where(
            CharacterVersion.id == version_id,
            CharacterVersion.workspace_id == workspace_id,
        )
    )
    if version is None:
        raise ResourceNotFound("Character version not found")
    return version


def get_style_version(
    session: Session, workspace_id: UUID, version_id: UUID
) -> StyleVersion:
    version = session.scalar(
        select(StyleVersion).where(
            StyleVersion.id == version_id,
            StyleVersion.workspace_id == workspace_id,
        )
    )
    if version is None:
        raise ResourceNotFound("Style version not found")
    return version


def set_default_style(
    session: Session,
    workspace_id: UUID,
    ip_id: UUID,
    style_version_id: UUID,
) -> IP:
    ip = _require_ip(session, workspace_id, ip_id)
    version = session.scalar(
        select(StyleVersion)
        .join(Style, Style.id == StyleVersion.style_id)
        .where(
            StyleVersion.id == style_version_id,
            StyleVersion.workspace_id == workspace_id,
            Style.ip_id == ip_id,
        )
    )
    if version is None:
        raise ResourceNotFound("Style version does not belong to this IP")
    if version.status != "approved":
        raise ResourceConflict("The default style must point to an approved version")
    ip.default_style_version_id = version.id
    session.commit()
    session.refresh(ip)
    return ip


def approve_asset_version(
    session: Session,
    workspace_id: UUID,
    ip_id: UUID,
    asset_id: UUID,
    version_id: UUID,
    approver_id: UUID,
) -> AssetVersion:
    _require_ip(session, workspace_id, ip_id)
    row = session.execute(
        select(Asset, AssetVersion)
        .join(AssetVersion, AssetVersion.asset_id == Asset.id)
        .where(
            Asset.id == asset_id,
            Asset.workspace_id == workspace_id,
            Asset.owner_ip_id == ip_id,
            AssetVersion.id == version_id,
        )
    ).first()
    if row is None:
        raise ResourceNotFound("Asset version not found")
    asset, version = row
    if version.status != "candidate":
        raise ResourceConflict("Only a candidate asset version can be approved")
    if session.scalar(
        select(AssetLink.id)
        .where(
            AssetLink.asset_version_id == version.id,
            AssetLink.owner_type == "generation_candidate",
        )
        .limit(1)
    ) is not None:
        raise ResourceConflict("Generation task candidates must be approved from candidate review")
    version.status = "approved"
    version.approved_at = datetime.now(timezone.utc)
    version.approved_by_user_id = approver_id
    latest_version_id = session.scalar(
        select(AssetVersion.id)
        .where(AssetVersion.asset_id == asset.id)
        .order_by(AssetVersion.version_no.desc())
        .limit(1)
    )
    if latest_version_id == version.id:
        asset.status = "approved"
    session.commit()
    session.refresh(version)
    return version
