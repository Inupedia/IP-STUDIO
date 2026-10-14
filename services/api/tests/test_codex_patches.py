from copy import deepcopy
import json
from pathlib import Path
from uuid import UUID

import pytest

from app.services.patch_validator import PatchValidationError, Scope, validate_canvas_patch

FIXTURE = Path(__file__).parents[3] / "packages" / "contracts" / "fixtures" / "canvas-v1.json"


def scope_for(document: dict[str, object] | None = None) -> Scope:
    canvas = deepcopy(document) if document is not None else json.loads(FIXTURE.read_text(encoding="utf-8"))
    return Scope(
        workspace_id=UUID("10000000-0000-4000-8000-000000000001"),
        ip_id=UUID("10000000-0000-4000-8000-000000000002"),
        episode_id=UUID(canvas["episode_id"]),
        document_id=UUID("10000000-0000-4000-8000-000000000020"),
        document=canvas,
        authorized_asset_version_ids=frozenset({UUID("00000000-0000-4000-8000-000000000003")}),
    )


def patch_for(scope: Scope, operations: list[dict[str, object]], **overrides: object) -> dict[str, object]:
    return {
        "workspace_id": str(scope.workspace_id),
        "ip_id": str(scope.ip_id),
        "episode_id": str(scope.episode_id),
        "document_id": str(scope.document_id),
        "base_revision": 5,
        "summary": "让回复更清楚",
        "operations": operations,
        **overrides,
    }


def test_valid_text_patch_returns_a_preview_without_mutating_the_source() -> None:
    scope = scope_for()
    source_before = deepcopy(scope.document)
    patch = patch_for(scope, [{
        "op": "set_text",
        "element_id": "00000000-0000-4000-8000-000000000010",
        "text": "在吗？（已更新）",
    }])

    validated = validate_canvas_patch(patch, scope, current_revision=5)

    original_message = scope.document["pages"][0]["panels"][0]["elements"][1]
    updated_message = validated.document["pages"][0]["panels"][0]["elements"][1]
    assert original_message["props"]["text"] == "在吗？"
    assert updated_message["props"]["text"] == "在吗？（已更新）"
    assert scope.document == source_before


def test_insert_element_adds_only_to_the_preview() -> None:
    scope = scope_for()
    source_before = deepcopy(scope.document)
    patch = patch_for(scope, [{
        "op": "insert_element",
        "panel_id": "00000000-0000-4000-8000-000000000008",
        "element": {
            "id": "00000000-0000-4000-8000-000000000012",
            "type": "text",
            "props": {"text": "新旁白"},
            "transform": {"x": 20, "y": 400, "width": 300, "height": 80},
            "z_index": 10,
        },
    }])

    validated = validate_canvas_patch(patch, scope, current_revision=5)

    preview_elements = validated.document["pages"][0]["panels"][0]["elements"]
    assert preview_elements[-1]["props"]["text"] == "新旁白"
    assert scope.document == source_before


def test_cross_ip_patch_is_denied() -> None:
    scope = scope_for()
    patch = patch_for(scope, [{
        "op": "set_text",
        "element_id": "00000000-0000-4000-8000-000000000010",
        "text": "不在。",
    }], ip_id="10000000-0000-4000-8000-000000000099")

    with pytest.raises(PatchValidationError, match="IP"):
        validate_canvas_patch(patch, scope, current_revision=5)


def test_locked_element_patch_is_denied() -> None:
    scope = scope_for()
    patch = patch_for(scope, [{
        "op": "replace_image_asset",
        "element_id": "00000000-0000-4000-8000-000000000009",
        "asset_version_id": "00000000-0000-4000-8000-000000000003",
    }])

    with pytest.raises(PatchValidationError, match="(?i)locked"):
        validate_canvas_patch(patch, scope, current_revision=5)


def test_unknown_operation_and_arbitrary_commands_are_denied() -> None:
    scope = scope_for()
    patch = patch_for(scope, [{"op": "execute_sql", "sql": "DELETE FROM assets"}])

    with pytest.raises(PatchValidationError, match="operation"):
        validate_canvas_patch(patch, scope, current_revision=5)


def test_stale_base_revision_is_denied() -> None:
    scope = scope_for()
    patch = patch_for(scope, [{
        "op": "set_text",
        "element_id": "00000000-0000-4000-8000-000000000010",
        "text": "不在。",
    }], base_revision=4)

    with pytest.raises(PatchValidationError, match="revision"):
        validate_canvas_patch(patch, scope, current_revision=5)


def test_cross_ip_asset_replacement_is_denied() -> None:
    scope = scope_for()
    patch = patch_for(scope, [{
        "op": "replace_image_asset",
        "element_id": "00000000-0000-4000-8000-000000000009",
        "asset_version_id": "10000000-0000-4000-8000-000000000099",
    }])
    unlocked = deepcopy(scope.document)
    unlocked["pages"][0]["panels"][0]["elements"][0]["locked"] = False
    scope = Scope(
        workspace_id=scope.workspace_id,
        ip_id=scope.ip_id,
        episode_id=scope.episode_id,
        document_id=scope.document_id,
        document=unlocked,
        authorized_asset_version_ids=scope.authorized_asset_version_ids,
    )

    with pytest.raises(PatchValidationError, match="(?i)asset version"):
        validate_canvas_patch(patch, scope, current_revision=5)


def test_transform_outside_canvas_bounds_is_denied() -> None:
    scope = scope_for()
    patch = patch_for(scope, [{
        "op": "set_transform",
        "element_id": "00000000-0000-4000-8000-000000000010",
        "transform": {"x": 0, "y": 0, "width": 40000, "height": 100, "rotation": 0},
    }])

    with pytest.raises(PatchValidationError, match="invalid"):
        validate_canvas_patch(patch, scope, current_revision=5)
