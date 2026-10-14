from __future__ import annotations

from copy import deepcopy
import json
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.assets import Asset, AssetVersion, Blob
from app.models.bibles import Character, CharacterVersion, Style, StyleVersion
from app.models.generation import GenerationTask
from app.models.ip import IP
from app.models.scripts import ScriptRevision
from app.models.story import Episode, Series
from app.services.prompt_builder import build_prompt

ASSET_VERSION_KEYS = (
    "standard_reference_asset_version_ids",
    "expression_asset_version_ids",
    "pose_asset_version_ids",
    "costume_asset_version_ids",
    "example_asset_version_ids",
)
MAX_FROZEN_REFERENCE_COUNT = 100


class ResourceNotFound(Exception):
    pass


class ResourceConflict(Exception):
    pass


def _require_episode(
    session: Session, workspace_id: UUID, episode_id: UUID
) -> tuple[Episode, UUID, UUID | None, UUID | None]:
    row = session.execute(
        select(Episode, Series.ip_id, Episode.default_style_version_id, IP.default_style_version_id)
        .join(Series, Series.id == Episode.series_id)
        .join(IP, IP.id == Series.ip_id)
        .where(
            Episode.id == episode_id,
            Episode.workspace_id == workspace_id,
            Series.workspace_id == workspace_id,
            IP.workspace_id == workspace_id,
        )
    ).first()
    if row is None:
        raise ResourceNotFound("Episode not found")
    return row[0], row[1], row[2], row[3]


def _find_panel(script_revision: ScriptRevision, panel_id: UUID) -> dict[str, Any]:
    panel_id_string = str(panel_id)
    panel_order = 0
    for scene in script_revision.script_json["scenes"]:
        for panel in scene["panels"]:
            panel_order += 1
            if str(panel["action_id"]) == panel_id_string:
                return {
                    "panel_id": panel_id,
                    "panel_order": panel_order,
                    "scene_id": scene["scene_id"],
                    "scene_name": scene["name"],
                    "location": scene["location"],
                    "time": scene["time"],
                    "action": panel["action"],
                    "shot_type": panel["shot_type"],
                    "no_text_prompt": panel["no_text_prompt"],
                    "character_version_ids": panel["character_version_ids"],
                    "background_asset_version_id": panel["background_asset_version_id"],
                }
    raise ResourceNotFound("Panel not found in this script revision")


def _bible_summary(bible: dict[str, object]) -> str:
    parts: list[str] = []
    for key in (
        "personality",
        "language_style",
        "fixed_appearance",
        "linework_rules",
        "palette",
        "lighting",
        "materials",
        "positive_rules",
        "negative_rules",
        "invariants",
        "prohibited_features",
    ):
        value = bible.get(key)
        if value:
            if isinstance(value, (dict, list)):
                rendered = json.dumps(value, ensure_ascii=False, sort_keys=True)
            else:
                rendered = str(value)
            parts.append(f"{key}: {rendered}")
    return "; ".join(parts)[:5000]


def _character_snapshots(
    session: Session,
    workspace_id: UUID,
    ip_id: UUID,
    version_ids: list[UUID],
) -> list[dict[str, object]]:
    if not version_ids:
        return []
    rows = session.execute(
        select(CharacterVersion, Character)
        .join(Character, Character.id == CharacterVersion.character_id)
        .where(
            CharacterVersion.id.in_(version_ids),
            CharacterVersion.workspace_id == workspace_id,
            Character.workspace_id == workspace_id,
        )
    ).all()
    found = {version.id: (version, character) for version, character in rows}
    if set(found) != set(version_ids) or any(
        character.ip_id != ip_id for _, character in found.values()
    ):
        raise ResourceNotFound("One or more character versions are not visible in this IP")
    if any(version.status != "approved" for version, _ in found.values()):
        raise ResourceConflict("Only approved character versions can be used for generation")
    return [
        {
            "kind": "character_version",
            "version_id": str(version.id),
            "entity_id": str(character.id),
            "version_no": version.version_no,
            "name": character.name,
            "bible": deepcopy(version.bible_json),
            "bible_summary": _bible_summary(version.bible_json),
        }
        for version_id in version_ids
        for version, character in [found[version_id]]
    ]


def _style_snapshots(
    session: Session,
    workspace_id: UUID,
    ip_id: UUID,
    version_ids: list[UUID],
) -> list[dict[str, object]]:
    if not version_ids:
        return []
    rows = session.execute(
        select(StyleVersion, Style)
        .join(Style, Style.id == StyleVersion.style_id)
        .where(
            StyleVersion.id.in_(version_ids),
            StyleVersion.workspace_id == workspace_id,
            Style.workspace_id == workspace_id,
        )
    ).all()
    found = {version.id: (version, style) for version, style in rows}
    if set(found) != set(version_ids) or any(
        style.ip_id != ip_id for _, style in found.values()
    ):
        raise ResourceNotFound("One or more style versions are not visible in this IP")
    if any(version.status != "approved" for version, _ in found.values()):
        raise ResourceConflict("Only approved style versions can be used for generation")
    return [
        {
            "kind": "style_version",
            "version_id": str(version.id),
            "entity_id": str(style.id),
            "version_no": version.version_no,
            "name": style.name,
            "bible": deepcopy(version.bible_json),
            "bible_summary": _bible_summary(version.bible_json),
        }
        for version_id in version_ids
        for version, style in [found[version_id]]
    ]


def _asset_snapshots(
    session: Session,
    workspace_id: UUID,
    ip_id: UUID,
    version_ids: list[UUID],
) -> list[dict[str, object]]:
    if not version_ids:
        return []
    rows = session.execute(
        select(AssetVersion, Asset, Blob)
        .join(Asset, Asset.id == AssetVersion.asset_id)
        .join(Blob, Blob.id == AssetVersion.blob_id)
        .where(
            AssetVersion.id.in_(version_ids),
            AssetVersion.workspace_id == workspace_id,
            Asset.workspace_id == workspace_id,
        )
    ).all()
    found = {version.id: (version, asset, blob) for version, asset, blob in rows}
    if set(found) != set(version_ids) or any(
        asset.owner_ip_id != ip_id for _, asset, _ in found.values()
    ):
        raise ResourceNotFound("One or more reference assets are not visible in this IP")
    if any(version.status != "approved" for version, _, _ in found.values()):
        raise ResourceConflict("Only approved asset versions can be used for generation")
    return [
        {
            "kind": "asset_version",
            "version_id": str(version.id),
            "asset_id": str(asset.id),
            "version_no": version.version_no,
            "name": asset.name,
            "asset_type": asset.type,
            "mime": blob.mime,
            "sha256": blob.sha256,
            "byte_size": blob.byte_size,
            "width": version.width,
            "height": version.height,
        }
        for version_id in version_ids
        for version, asset, blob in [found[version_id]]
    ]


def _unique(values: list[UUID]) -> list[UUID]:
    return list(dict.fromkeys(values))


def _bible_asset_ids(references: list[dict[str, object]]) -> list[UUID]:
    result: list[UUID] = []
    for reference in references:
        bible = reference.get("bible", {})
        if isinstance(bible, dict):
            for key in ASSET_VERSION_KEYS:
                result.extend(UUID(str(asset_id)) for asset_id in bible.get(key, []))
    return result


def create_generation_task(
    session: Session,
    workspace_id: UUID,
    episode_id: UUID,
    script_revision_no: int,
    panel_id: UUID,
    reference_version_ids: list[UUID],
    mode: str = "chatgpt_web",
) -> GenerationTask:
    if mode != "chatgpt_web":
        raise ResourceConflict("Only manual ChatGPT Web generation is available")
    _episode, ip_id, episode_style_id, ip_style_id = _require_episode(
        session, workspace_id, episode_id
    )
    script_revision = session.scalar(
        select(ScriptRevision).where(
            ScriptRevision.episode_id == episode_id,
            ScriptRevision.workspace_id == workspace_id,
            ScriptRevision.revision_no == script_revision_no,
        )
    )
    if script_revision is None:
        raise ResourceNotFound("Script revision not found")
    panel = _find_panel(script_revision, panel_id)

    character_ids = [UUID(str(value)) for value in panel["character_version_ids"]]
    style_ids = [value for value in [episode_style_id or ip_style_id] if value is not None]
    asset_ids = [UUID(str(value)) for value in [panel["background_asset_version_id"]] if value]
    remaining: list[UUID] = []
    for reference_id in _unique(reference_version_ids):
        if session.scalar(select(CharacterVersion.id).where(CharacterVersion.id == reference_id)):
            character_ids.append(reference_id)
        elif session.scalar(select(StyleVersion.id).where(StyleVersion.id == reference_id)):
            style_ids.append(reference_id)
        elif session.scalar(select(AssetVersion.id).where(AssetVersion.id == reference_id)):
            asset_ids.append(reference_id)
        else:
            remaining.append(reference_id)
    if remaining:
        raise ResourceNotFound("One or more reference versions do not exist")

    character_refs = _character_snapshots(session, workspace_id, ip_id, _unique(character_ids))
    style_refs = _style_snapshots(session, workspace_id, ip_id, _unique(style_ids))
    asset_ids.extend(_bible_asset_ids(character_refs + style_refs))
    all_asset_ids = _unique(asset_ids)
    if len(character_refs) + len(style_refs) + len(all_asset_ids) > MAX_FROZEN_REFERENCE_COUNT:
        raise ResourceConflict("A generation task can freeze at most 100 reference versions")
    asset_refs = _asset_snapshots(session, workspace_id, ip_id, all_asset_ids)
    refs = character_refs + style_refs + asset_refs
    prompt_snapshot = build_prompt(panel, refs)
    task = GenerationTask(
        workspace_id=workspace_id,
        episode_id=episode_id,
        script_revision_id=script_revision.id,
        script_revision_no=script_revision.revision_no,
        panel_id=panel_id,
        mode=mode,
        status="prepared",
        prompt_snapshot=prompt_snapshot,
        reference_snapshot=refs,
    )
    session.add(task)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise ResourceConflict("Generation task could not be created") from error
    session.refresh(task)
    return task


def get_generation_task(session: Session, workspace_id: UUID, task_id: UUID) -> GenerationTask:
    task = session.scalar(
        select(GenerationTask).where(
            GenerationTask.id == task_id,
            GenerationTask.workspace_id == workspace_id,
        )
    )
    if task is None:
        raise ResourceNotFound("Generation task not found")
    return task


def start_manual_generation(
    session: Session, workspace_id: UUID, task_id: UUID
) -> GenerationTask:
    task = get_generation_task(session, workspace_id, task_id)
    if task.mode != "chatgpt_web" or task.status != "prepared":
        raise ResourceConflict("Only a prepared manual task can enter waiting_manual_generation")
    task.status = "waiting_manual_generation"
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise ResourceConflict("Generation task status could not be updated") from error
    session.refresh(task)
    return task
