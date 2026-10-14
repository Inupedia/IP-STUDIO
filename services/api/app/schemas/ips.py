import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class IPCreate(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=120)
    summary: str | None = Field(default=None, max_length=4000)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        code = value.strip().upper()
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9_-]{0,31}", code):
            raise ValueError("Use letters, numbers, hyphens, or underscores for the IP code")
        return code

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        name = value.strip()
        if not name:
            raise ValueError("IP name cannot be blank")
        return name


class IPRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    summary: str | None
    status: str
    created_at: datetime


class SeriesCreate(BaseModel):
    ip_id: UUID
    name: str = Field(min_length=1, max_length=120)
    summary: str | None = Field(default=None, max_length=4000)

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        name = value.strip()
        if not name:
            raise ValueError("Series name cannot be blank")
        return name


class SeriesRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ip_id: UUID
    name: str
    summary: str | None
    created_at: datetime


class EpisodeCreate(BaseModel):
    number: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=200)

    @field_validator("title")
    @classmethod
    def trim_title(cls, value: str) -> str:
        title = value.strip()
        if not title:
            raise ValueError("Episode title cannot be blank")
        return title


class EpisodeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    series_id: UUID
    number: int
    title: str
    status: str
    created_at: datetime
