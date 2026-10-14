from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class GenerationCandidateCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_version_id: UUID


class GenerationCandidateRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: UUID
    task_id: UUID
    panel_id: UUID
    asset_id: UUID
    asset_version_id: UUID
    asset_name: str
    asset_type: str
    version_no: int
    mime: str
    sha256: str
    byte_size: int
    width: int
    height: int
    status: Literal["pending_review", "approved", "rejected"]
    created_at: datetime
    reviewed_at: datetime | None
    reviewed_by_user_id: UUID | None
    review_note: str | None


class GenerationCandidateReviewNote(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_note: str | None = None
