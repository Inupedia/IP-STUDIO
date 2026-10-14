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
    asset_version_id: UUID
    status: Literal["pending_review", "approved", "rejected"]
    created_at: datetime
