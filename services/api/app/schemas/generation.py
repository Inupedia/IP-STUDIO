from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GenerationTaskCreate(StrictModel):
    script_revision_no: int = Field(ge=1)
    panel_id: UUID
    reference_version_ids: list[UUID] = Field(default_factory=list, max_length=100)
    mode: Literal["chatgpt_web"] = "chatgpt_web"


class GenerationTaskRead(StrictModel):
    task_id: UUID
    episode_id: UUID
    script_revision_id: UUID
    script_revision_no: int
    panel_id: UUID
    mode: Literal["chatgpt_web"]
    status: Literal["prepared", "waiting_manual_generation", "asset_imported"]
    prompt_snapshot: dict[str, object]
    reference_snapshot: list[dict[str, object]]
    reference_bundle_url: str
    created_at: datetime
