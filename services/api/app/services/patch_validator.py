from copy import deepcopy
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from pydantic import ValidationError

from app.codex.patches import (
    CanvasPatch,
    InsertElementOperation,
    RemoveElementOperation,
    ReplaceImageAssetOperation,
    SetTextOperation,
    SetTransformOperation,
)
from app.schemas.canvas import CanvasDocument


class PatchValidationError(Exception):
    pass


@dataclass(frozen=True)
class Scope:
    workspace_id: UUID
    ip_id: UUID
    episode_id: UUID
    document_id: UUID
    document: dict[str, Any]
    authorized_asset_version_ids: frozenset[UUID]


@dataclass(frozen=True)
class ValidatedPatch:
    patch: CanvasPatch
    document: dict[str, Any]


def _all_elements(document: dict[str, Any]) -> list[tuple[dict[str, Any], int, dict[str, Any]]]:
    return [
        (panel, index, element)
        for page in document["pages"]
        for panel in page["panels"]
        for index, element in enumerate(panel["elements"])
    ]


def _find_element(document: dict[str, Any], element_id: UUID) -> tuple[dict[str, Any], int, dict[str, Any]]:
    matches = [item for item in _all_elements(document) if item[2]["id"] == str(element_id)]
    if len(matches) != 1:
        raise PatchValidationError("Patch element does not exist uniquely in this document")
    return matches[0]


def _assert_editable(element: dict[str, Any]) -> None:
    if element.get("locked") or element["type"] == "panel_frame":
        raise PatchValidationError("Locked or brand-shell elements cannot be changed by a patch")


def _assert_asset_authorized(asset_version_id: UUID, scope: Scope) -> None:
    if asset_version_id not in scope.authorized_asset_version_ids:
        raise PatchValidationError("Asset version is not approved and authorized in this IP")


def _validate_operation(patch_operation: Any, document: dict[str, Any], scope: Scope) -> None:
    if isinstance(patch_operation, SetTextOperation):
        _, _, element = _find_element(document, patch_operation.element_id)
        _assert_editable(element)
        if element["type"] not in {"text", "speech_bubble", "thought_bubble", "chat_message"}:
            raise PatchValidationError("Patch target does not contain editable text")
        element["props"]["text"] = patch_operation.text
        return

    if isinstance(patch_operation, SetTransformOperation):
        _, _, element = _find_element(document, patch_operation.element_id)
        _assert_editable(element)
        element["transform"] = patch_operation.transform.model_dump(mode="json")
        return

    if isinstance(patch_operation, ReplaceImageAssetOperation):
        _, _, element = _find_element(document, patch_operation.element_id)
        _assert_editable(element)
        if element["type"] not in {"image", "sticker"}:
            raise PatchValidationError("Patch target is not a replaceable image")
        _assert_asset_authorized(patch_operation.asset_version_id, scope)
        element["asset_version_id"] = str(patch_operation.asset_version_id)
        return

    if isinstance(patch_operation, InsertElementOperation):
        if patch_operation.element.type == "panel_frame":
            raise PatchValidationError("A patch cannot insert a brand or panel frame")
        if patch_operation.element.locked:
            raise PatchValidationError("Codex cannot create a locked element")
        if any(element["id"] == str(patch_operation.element.id) for _, _, element in _all_elements(document)):
            raise PatchValidationError("Patch element ID already exists")
        panels = [
            panel
            for page in document["pages"]
            for panel in page["panels"]
            if panel["id"] == str(patch_operation.panel_id)
        ]
        if len(panels) != 1:
            raise PatchValidationError("Patch panel does not exist uniquely in this document")
        if patch_operation.element.type in {"image", "sticker"}:
            _assert_asset_authorized(patch_operation.element.asset_version_id, scope)
        panels[0]["elements"].append(patch_operation.element.model_dump(mode="json"))
        return

    if isinstance(patch_operation, RemoveElementOperation):
        panel, index, element = _find_element(document, patch_operation.element_id)
        _assert_editable(element)
        panel["elements"].pop(index)
        return

    raise PatchValidationError("Unknown patch operation")


def validate_canvas_patch(
    patch: CanvasPatch | dict[str, Any],
    scope: Scope,
    current_revision: int,
) -> ValidatedPatch:
    try:
        parsed_patch = patch if isinstance(patch, CanvasPatch) else CanvasPatch.model_validate(patch)
        current_document = CanvasDocument.model_validate(scope.document).model_dump(mode="json")
    except ValidationError as error:
        raise PatchValidationError("Patch operation or canvas document is invalid") from error

    if parsed_patch.workspace_id != scope.workspace_id:
        raise PatchValidationError("Patch workspace does not match the authorized workspace")
    if parsed_patch.ip_id != scope.ip_id:
        raise PatchValidationError("Patch IP does not match the authorized IP")
    if parsed_patch.episode_id != scope.episode_id or parsed_patch.episode_id != UUID(current_document["episode_id"]):
        raise PatchValidationError("Patch episode does not match the authorized episode")
    if parsed_patch.document_id != scope.document_id:
        raise PatchValidationError("Patch document does not match the authorized document")
    if parsed_patch.base_revision != current_revision or current_document["revision"] != current_revision:
        raise PatchValidationError("Patch base revision is stale")

    updated_document = deepcopy(current_document)
    for operation in parsed_patch.operations:
        _validate_operation(operation, updated_document, scope)
    try:
        validated_document = CanvasDocument.model_validate(updated_document)
    except ValidationError as error:
        raise PatchValidationError("Patch produces an invalid canvas document") from error
    return ValidatedPatch(
        patch=parsed_patch,
        document=validated_document.model_dump(mode="json"),
    )
