from copy import deepcopy
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.assets import Asset, AssetVersion
from app.models.bibles import Character, CharacterVersion
from app.models.documents import EpisodeDocument
from app.models.scripts import ScriptRevision
from app.models.story import Episode, Series
from app.services.documents import ResourceConflict as DocumentConflict
from app.services.documents import ResourceNotFound as DocumentNotFound
from app.services.documents import save_document


class ResourceNotFound(Exception):
    pass


class ResourceConflict(Exception):
    pass


class DialogueSyncRequired(ResourceConflict):
    def __init__(self, changes: list[dict[str, object]]) -> None:
        super().__init__("剧本对白与画布中已有对白文字不同；确认后才会同步")
        self.changes = changes


def _require_episode(session: Session, workspace_id: UUID, episode_id: UUID) -> tuple[Episode, UUID]:
    row = session.execute(
        select(Episode, Series.ip_id)
        .join(Series, Series.id == Episode.series_id)
        .where(
            Episode.id == episode_id,
            Episode.workspace_id == workspace_id,
            Series.workspace_id == workspace_id,
        )
    ).first()
    if row is None:
        raise ResourceNotFound("Episode not found")
    return row[0], row[1]


def _validate_references(
    session: Session, workspace_id: UUID, ip_id: UUID, script: dict[str, object]
) -> None:
    scenes = script["scenes"]
    character_ids = {
        UUID(str(character_id))
        for scene in scenes  # type: ignore[union-attr]
        for character_id in scene["character_version_ids"]
    }
    character_ids.update(
        UUID(str(character_id))
        for scene in scenes  # type: ignore[union-attr]
        for dialogue in scene["dialogues"]
        if dialogue.get("character_version_id")
        for character_id in [dialogue["character_version_id"]]
    )
    character_ids.update(
        UUID(str(character_id))
        for scene in scenes  # type: ignore[union-attr]
        for panel in scene["panels"]
        for character_id in panel["character_version_ids"]
    )
    if character_ids:
        rows = session.execute(
            select(CharacterVersion.id, CharacterVersion.status, Character.ip_id)
            .join(Character, Character.id == CharacterVersion.character_id)
            .where(
                CharacterVersion.id.in_(character_ids),
                CharacterVersion.workspace_id == workspace_id,
                Character.workspace_id == workspace_id,
            )
        )
        found = {version_id: (status, owner_ip_id) for version_id, status, owner_ip_id in rows}
        if set(found) != character_ids or any(owner_ip_id != ip_id for _, owner_ip_id in found.values()):
            raise ResourceNotFound("One or more character versions are not visible in this IP")
        if any(status != "approved" for status, _ in found.values()):
            raise ResourceConflict("Only approved character versions can be used by a script")

    asset_ids = {
        UUID(str(panel["background_asset_version_id"]))
        for scene in scenes  # type: ignore[union-attr]
        for panel in scene["panels"]
        if panel.get("background_asset_version_id")
    }
    if asset_ids:
        rows = session.execute(
            select(AssetVersion.id, AssetVersion.status, Asset.owner_ip_id)
            .join(Asset, Asset.id == AssetVersion.asset_id)
            .where(
                AssetVersion.id.in_(asset_ids),
                AssetVersion.workspace_id == workspace_id,
                Asset.workspace_id == workspace_id,
            )
        )
        found = {version_id: (status, owner_ip_id) for version_id, status, owner_ip_id in rows}
        if set(found) != asset_ids or any(owner_ip_id != ip_id for _, owner_ip_id in found.values()):
            raise ResourceNotFound("One or more background assets are not visible in this IP")
        if any(status != "approved" for status, _ in found.values()):
            raise ResourceConflict("Only approved background assets can be used by a script")


def create_script_revision(
    session: Session,
    workspace_id: UUID,
    episode_id: UUID,
    base_revision: int,
    script: dict[str, object],
    source_markdown: str | None = None,
    note: str | None = None,
) -> ScriptRevision:
    _episode, ip_id = _require_episode(session, workspace_id, episode_id)
    _validate_references(session, workspace_id, ip_id, script)
    latest_revision = session.scalar(
        select(func.max(ScriptRevision.revision_no)).where(
            ScriptRevision.episode_id == episode_id,
            ScriptRevision.workspace_id == workspace_id,
        )
    ) or 0
    if latest_revision != base_revision:
        raise ResourceConflict("Script revision changed; reload the latest version")
    revision = ScriptRevision(
        workspace_id=workspace_id,
        episode_id=episode_id,
        revision_no=latest_revision + 1,
        source_markdown=source_markdown,
        script_json=deepcopy(script),
        note=note,
    )
    session.add(revision)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise ResourceConflict("Script revision changed; reload the latest version") from error
    session.refresh(revision)
    return revision


def list_script_revisions(session: Session, workspace_id: UUID, episode_id: UUID) -> list[ScriptRevision]:
    _require_episode(session, workspace_id, episode_id)
    return list(
        session.scalars(
            select(ScriptRevision)
            .where(
                ScriptRevision.episode_id == episode_id,
                ScriptRevision.workspace_id == workspace_id,
            )
            .order_by(ScriptRevision.revision_no.desc())
        )
    )


def get_script_revision(
    session: Session, workspace_id: UUID, episode_id: UUID, revision_no: int
) -> ScriptRevision:
    _require_episode(session, workspace_id, episode_id)
    revision = session.scalar(
        select(ScriptRevision).where(
            ScriptRevision.episode_id == episode_id,
            ScriptRevision.workspace_id == workspace_id,
            ScriptRevision.revision_no == revision_no,
        )
    )
    if revision is None:
        raise ResourceNotFound("Script revision not found")
    return revision


def _materialized_panels(script_revision: ScriptRevision) -> list[dict[str, object]]:
    script = script_revision.script_json
    panels: list[dict[str, object]] = []
    panel_order = 0
    for scene in script["scenes"]:  # type: ignore[index]
        dialogues_by_id = {str(item["dialogue_id"]): item for item in scene["dialogues"]}
        for plan in scene["panels"]:
            panel_order += 1
            panels.append({
                "panel_id": plan["action_id"],
                "panel_order": panel_order,
                "scene_id": scene["scene_id"],
                "scene_name": scene["name"],
                "location": scene["location"],
                "time": scene["time"],
                "action": plan["action"],
                "shot_type": plan["shot_type"],
                "character_version_ids": plan["character_version_ids"],
                "background_asset_version_id": plan["background_asset_version_id"],
                "no_text_prompt": plan["no_text_prompt"],
                "dialogues": [dialogues_by_id[str(dialogue_id)] for dialogue_id in plan["dialogue_ids"]],
            })
    return panels


def _document_dialogue_changes(
    document: dict[str, object] | None, panels: list[dict[str, object]]
) -> list[dict[str, object]]:
    if document is None:
        return []
    pages = sorted(document["pages"], key=lambda page: page["order"])  # type: ignore[index]
    canvas_panels = [panel for page in pages for panel in page["panels"]]
    changes: list[dict[str, object]] = []
    for panel_plan, canvas_panel in zip(panels, canvas_panels, strict=False):
        planned_dialogues = panel_plan["dialogues"]
        canvas_dialogues = {
            element_type: sorted(
                (element for element in canvas_panel["elements"] if element["type"] == element_type),
                key=lambda element: element["z_index"],
            )
            for element_type in ("chat_message", "speech_bubble")
        }
        consumed = {"chat_message": 0, "speech_bubble": 0}
        for dialogue in planned_dialogues:
            expected_type = "chat_message" if dialogue["kind"] == "chat_message" else "speech_bubble"
            index = consumed[expected_type]
            if index >= len(canvas_dialogues[expected_type]):
                continue
            element = canvas_dialogues[expected_type][index]
            consumed[expected_type] += 1
            if dialogue["text"] != element["props"]["text"]:
                changes.append({
                    "panel_order": panel_plan["panel_order"],
                    "element_id": element["id"],
                    "old_text": element["props"]["text"],
                    "new_text": dialogue["text"],
                })
    return changes


def _apply_dialogue_changes(
    document: dict[str, object], changes: list[dict[str, object]]
) -> dict[str, object]:
    updated = deepcopy(document)
    values = {str(change["element_id"]): change["new_text"] for change in changes}
    for page in updated["pages"]:  # type: ignore[index]
        for panel in page["panels"]:
            for element in panel["elements"]:
                if element["id"] in values:
                    element["props"]["text"] = values[element["id"]]
    return updated


def materialize_panels(
    session: Session,
    workspace_id: UUID,
    episode_id: UUID,
    revision_no: int,
    base_document_revision: int,
    confirm_dialogue_sync: bool = False,
) -> dict[str, object]:
    _require_episode(session, workspace_id, episode_id)
    script_revision = get_script_revision(session, workspace_id, episode_id, revision_no)
    panels = _materialized_panels(script_revision)
    document_state = session.scalar(
        select(EpisodeDocument).where(
            EpisodeDocument.episode_id == episode_id,
            EpisodeDocument.workspace_id == workspace_id,
        )
    )
    document = deepcopy(document_state.document_json) if document_state else None
    current_document_revision = document_state.current_revision if document_state else 0
    changes = _document_dialogue_changes(document, panels)
    if changes and not confirm_dialogue_sync:
        raise DialogueSyncRequired(changes)

    synced_count = 0
    if changes and document is not None:
        if current_document_revision != base_document_revision:
            raise ResourceConflict("Canvas document revision changed; reload before syncing script dialogues")
        try:
            next_document_revision, _ = save_document(
                session,
                workspace_id,
                episode_id,
                base_document_revision,
                _apply_dialogue_changes(document, changes),
                note=f"Sync dialogues from script revision {revision_no}",
            )
        except DocumentNotFound as error:
            raise ResourceNotFound(str(error)) from error
        except DocumentConflict as error:
            raise ResourceConflict(str(error)) from error
        current_document_revision = next_document_revision
        synced_count = len(changes)

    return {
        "script_revision_no": revision_no,
        "document_revision": current_document_revision,
        "panels": panels,
        "synced_dialogue_count": synced_count,
        "dialogue_changes": changes,
    }
