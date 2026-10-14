from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class LockedElement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=80)
    kind: Literal["background", "logo", "decoration", "title_bar", "footer"]
    locked: Literal[True] = True
    x: float = Field(ge=0)
    y: float = Field(ge=0)
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    asset_version_id: UUID | None = None
    fill: str | None = Field(default=None, max_length=64)
    opacity: float = Field(default=1, ge=0, le=1)


class DynamicSlot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float = Field(ge=0)
    y: float = Field(ge=0)
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    font_family: str = Field(default="sans-serif", max_length=120)
    font_size: float = Field(default=48, gt=0, le=512)
    color: str = Field(default="#242923", max_length=64)
    align: Literal["left", "center", "right"] = "left"


class BrandTemplateV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    width: int = Field(gt=0, le=8192)
    height: int = Field(gt=0, le=8192)
    locked_elements: list[LockedElement] = Field(min_length=1, max_length=100)
    dynamic_slots: dict[Literal["title", "episode_number"], DynamicSlot]

    @field_validator("dynamic_slots")
    @classmethod
    def required_dynamic_slots(
        cls, slots: dict[str, DynamicSlot]
    ) -> dict[str, DynamicSlot]:
        if set(slots) != {"title", "episode_number"}:
            raise ValueError("Brand templates require title and episode_number dynamic slots")
        return slots

    @field_validator("locked_elements")
    @classmethod
    def unique_element_ids(cls, elements: list[LockedElement]) -> list[LockedElement]:
        ids = [element.id for element in elements]
        if len(ids) != len(set(ids)):
            raise ValueError("Brand element ids must be unique")
        return elements

    @model_validator(mode="after")
    def elements_fit_page(self) -> "BrandTemplateV1":
        for element in self.locked_elements:
            if element.x + element.width > self.width or element.y + element.height > self.height:
                raise ValueError(f"Brand element {element.id} falls outside the page")
        for slot_name, slot in self.dynamic_slots.items():
            if slot.x + slot.width > self.width or slot.y + slot.height > self.height:
                raise ValueError(f"Dynamic slot {slot_name} falls outside the page")
        return self


class BrandTemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    template: BrandTemplateV1

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        name = value.strip()
        if not name:
            raise ValueError("Brand template name cannot be blank")
        return name


class BrandTemplateVersionCandidate(BaseModel):
    base_version_id: UUID
    template: BrandTemplateV1


class BrandTemplateVersionRead(BaseModel):
    brand_template_version_id: UUID
    brand_template_id: UUID
    version_no: int
    status: str
    template: dict[str, object]
    derived_from_version_id: UUID | None
    approved_at: datetime | None


class BrandTemplateRead(BaseModel):
    brand_template_id: UUID
    ip_id: UUID
    name: str
    versions: list[BrandTemplateVersionRead]
