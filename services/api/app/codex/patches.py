from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.canvas import CanvasElement, Transform


class PatchOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SetTextOperation(PatchOperation):
    op: Literal["set_text"]
    element_id: UUID
    text: str = Field(max_length=10_000)


class SetTransformOperation(PatchOperation):
    op: Literal["set_transform"]
    element_id: UUID
    transform: Transform


class ReplaceImageAssetOperation(PatchOperation):
    op: Literal["replace_image_asset"]
    element_id: UUID
    asset_version_id: UUID


class InsertElementOperation(PatchOperation):
    op: Literal["insert_element"]
    panel_id: UUID
    element: CanvasElement


class RemoveElementOperation(PatchOperation):
    op: Literal["remove_element"]
    element_id: UUID


CanvasPatchOperation = Annotated[
    SetTextOperation
    | SetTransformOperation
    | ReplaceImageAssetOperation
    | InsertElementOperation
    | RemoveElementOperation,
    Field(discriminator="op"),
]


class CanvasPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workspace_id: UUID
    ip_id: UUID
    episode_id: UUID
    document_id: UUID
    base_revision: int = Field(ge=0)
    summary: str = Field(min_length=1, max_length=500)
    operations: list[CanvasPatchOperation] = Field(min_length=1, max_length=50)


class PatchDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=500)
    operations: list[CanvasPatchOperation] = Field(min_length=1, max_length=50)
