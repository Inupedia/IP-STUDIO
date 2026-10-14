from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.codex.patches import CanvasPatch
from app.schemas.canvas import CanvasDocument


class CodexPatchCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instruction: str = Field(min_length=1, max_length=4000)


class CodexPatchApprove(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_revision: int = Field(ge=0)
    approval_id: UUID


class CodexPatchReject(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_note: str | None = Field(default=None, max_length=1000)


class CodexPatchProposalRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patch_id: UUID
    approval_id: UUID
    workspace_id: UUID
    ip_id: UUID
    episode_id: UUID
    document_id: UUID
    base_revision: int
    patch: CanvasPatch
    preview_document: CanvasDocument
    status: Literal["pending_approval", "approved", "rejected"]
    created_by_user_id: UUID
    reviewed_by_user_id: UUID | None
    reviewed_at: datetime | None
    review_note: str | None
    applied_revision: int | None
    created_at: datetime
