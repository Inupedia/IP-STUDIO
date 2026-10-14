from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CodexRunRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: UUID
    task_id: UUID
    panel_id: UUID
    status: Literal["queued", "running", "candidate_ready", "failed"]
    candidate_id: UUID | None
    started_at: datetime | None
    completed_at: datetime | None
    error_reason: str | None
    created_at: datetime
