import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CharacterBible(BaseModel):
    model_config = ConfigDict(extra="forbid")

    personality: str = ""
    language_style: str = ""
    fixed_appearance: str = ""
    invariants: list[str] = Field(default_factory=list)
    palette: dict[str, str] = Field(default_factory=dict)
    prohibited_features: list[str] = Field(default_factory=list)
    standard_reference_asset_version_ids: list[UUID] = Field(default_factory=list)
    expression_asset_version_ids: list[UUID] = Field(default_factory=list)
    pose_asset_version_ids: list[UUID] = Field(default_factory=list)
    costume_asset_version_ids: list[UUID] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class StyleBible(BaseModel):
    model_config = ConfigDict(extra="forbid")

    linework_rules: list[str] = Field(default_factory=list)
    palette: dict[str, str] = Field(default_factory=dict)
    lighting: str = ""
    materials: list[str] = Field(default_factory=list)
    aspect_ratios: list[str] = Field(default_factory=list)
    positive_rules: list[str] = Field(default_factory=list)
    negative_rules: list[str] = Field(default_factory=list)
    example_asset_version_ids: list[UUID] = Field(default_factory=list)
    font_rules: str = ""
    speech_bubble_rules: str = ""
    tags: list[str] = Field(default_factory=list)


class CharacterCreate(BaseModel):
    code: str = Field(min_length=1, max_length=48)
    name: str = Field(min_length=1, max_length=120)
    bible: CharacterBible

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        code = value.strip().upper()
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9_-]{0,47}", code):
            raise ValueError("Use letters, numbers, hyphens, or underscores for the character code")
        return code

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        name = value.strip()
        if not name:
            raise ValueError("Character name cannot be blank")
        return name


class StyleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    bible: StyleBible

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        name = value.strip()
        if not name:
            raise ValueError("Style name cannot be blank")
        return name


class CharacterVersionCandidate(BaseModel):
    base_version_id: UUID | None = None
    bible: CharacterBible


class StyleVersionCandidate(BaseModel):
    base_version_id: UUID | None = None
    bible: StyleBible


class CharacterVersionRead(BaseModel):
    character_version_id: UUID
    character_id: UUID
    version_no: int
    status: str
    bible: dict[str, object]
    derived_from_version_id: UUID | None
    approved_at: datetime | None


class StyleVersionRead(BaseModel):
    style_version_id: UUID
    style_id: UUID
    version_no: int
    status: str
    bible: dict[str, object]
    derived_from_version_id: UUID | None
    approved_at: datetime | None


class CharacterRead(BaseModel):
    character_id: UUID
    ip_id: UUID
    code: str
    name: str
    versions: list[CharacterVersionRead]


class StyleRead(BaseModel):
    style_id: UUID
    ip_id: UUID
    name: str
    versions: list[StyleVersionRead]


class DefaultStyleUpdate(BaseModel):
    style_version_id: UUID


class DefaultStyleRead(BaseModel):
    ip_id: UUID
    default_style_version_id: UUID
