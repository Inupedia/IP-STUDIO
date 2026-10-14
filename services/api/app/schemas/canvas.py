from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Transform(StrictModel):
    x: float = Field(ge=-32768, le=32768)
    y: float = Field(ge=-32768, le=32768)
    width: float = Field(gt=0, le=32768)
    height: float = Field(gt=0, le=32768)
    rotation: float = Field(default=0, ge=-3600, le=3600)


class Crop(StrictModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def within_normalized_bounds(self) -> "Crop":
        if self.x + self.width > 1 or self.y + self.height > 1:
            raise ValueError("Crop rectangle must fit within normalized image bounds")
        return self


class ElementBase(StrictModel):
    id: UUID
    transform: Transform
    opacity: float = Field(default=1, ge=0, le=1)
    z_index: int = Field(ge=0)
    locked: bool = False


class ImageElement(ElementBase):
    type: Literal["image"]
    asset_version_id: UUID
    crop: Crop = Field(default_factory=lambda: Crop(x=0, y=0, width=1, height=1))


class TextProps(StrictModel):
    text: str = Field(max_length=10000)
    font_family: str = Field(default="sans-serif", max_length=120)
    font_size: float = Field(default=32, gt=0, le=512)
    font_weight: int = Field(default=400, ge=100, le=900)
    color: str = Field(default="#242923", max_length=64)
    align: Literal["left", "center", "right"] = "left"
    line_height: float = Field(default=1.3, gt=0, le=10)
    letter_spacing: float = Field(default=0, ge=-20, le=100)


class TextElement(ElementBase):
    type: Literal["text"]
    props: TextProps


class BubbleProps(StrictModel):
    text: str = Field(max_length=10000)
    shape: Literal["rounded_rectangle", "ellipse", "cloud"] = "rounded_rectangle"
    fill: str = Field(default="#ffffff", max_length=64)
    stroke: str = Field(default="#242923", max_length=64)
    stroke_width: float = Field(default=2, ge=0, le=64)
    tail_position: Literal["left", "right", "top", "bottom", "none"] = "bottom"
    font_family: str = Field(default="sans-serif", max_length=120)
    font_size: float = Field(default=28, gt=0, le=512)


class SpeechBubbleElement(ElementBase):
    type: Literal["speech_bubble"]
    props: BubbleProps


class ThoughtBubbleElement(ElementBase):
    type: Literal["thought_bubble"]
    props: BubbleProps


class ChatMessageProps(StrictModel):
    self_participant_id: UUID
    sender_id: UUID
    text: str = Field(max_length=10000)
    sent_at: str = Field(max_length=40)
    theme: Literal["light", "dark"] = "light"
    direction_override: Literal["left", "right"] | None = None


class ChatMessageElement(ElementBase):
    type: Literal["chat_message"]
    props: ChatMessageProps


class ShapeProps(StrictModel):
    shape: Literal["rectangle", "rounded_rectangle", "ellipse", "line", "arrow"]
    fill: str | None = Field(default=None, max_length=64)
    stroke: str = Field(default="#242923", max_length=64)
    stroke_width: float = Field(default=2, ge=0, le=64)


class ShapeElement(ElementBase):
    type: Literal["shape"]
    props: ShapeProps


class StickerElement(ElementBase):
    type: Literal["sticker"]
    asset_version_id: UUID


class PanelFrameProps(StrictModel):
    stroke: str = Field(default="#242923", max_length=64)
    stroke_width: float = Field(default=2, ge=0, le=64)
    fill: str | None = Field(default=None, max_length=64)


class PanelFrameElement(ElementBase):
    type: Literal["panel_frame"]
    props: PanelFrameProps


CanvasElement = Annotated[
    ImageElement
    | TextElement
    | SpeechBubbleElement
    | ThoughtBubbleElement
    | ChatMessageElement
    | ShapeElement
    | StickerElement
    | PanelFrameElement,
    Field(discriminator="type"),
]


class Rect(StrictModel):
    x: float = Field(ge=0)
    y: float = Field(ge=0)
    width: float = Field(gt=0)
    height: float = Field(gt=0)


class CanvasPanel(StrictModel):
    id: UUID
    rect: Rect
    elements: list[CanvasElement]


class CanvasPage(StrictModel):
    id: UUID
    width: int = Field(gt=0, le=8192)
    height: int = Field(gt=0, le=8192)
    order: int = Field(gt=0)
    layout_code: Literal["four", "six", "eight", "custom"]
    brand_template_version_id: UUID
    panels: list[CanvasPanel] = Field(min_length=1)

    @model_validator(mode="after")
    def panels_fit_page(self) -> "CanvasPage":
        for panel in self.panels:
            if panel.rect.x + panel.rect.width > self.width or panel.rect.y + panel.rect.height > self.height:
                raise ValueError(f"Panel {panel.id} falls outside the page")
        return self


class DynamicFields(StrictModel):
    title: str = Field(max_length=1000)
    episode_number: str = Field(max_length=32)


class CanvasDocument(StrictModel):
    schema_version: Literal["1.0"]
    episode_id: UUID
    revision: int = Field(ge=0)
    style_version_id: UUID | None
    brand_template_version_id: UUID
    dynamic_fields: DynamicFields
    pages: list[CanvasPage] = Field(min_length=1)

    @model_validator(mode="after")
    def consistent_page_versions(self) -> "CanvasDocument":
        orders = [page.order for page in self.pages]
        if len(orders) != len(set(orders)):
            raise ValueError("Page order values must be unique")
        if any(page.brand_template_version_id != self.brand_template_version_id for page in self.pages):
            raise ValueError("Every page must use the document brand template version")
        return self


def resolve_message_side(sender_id: str, self_id: str) -> Literal["left", "right"]:
    return "right" if sender_id == self_id else "left"
