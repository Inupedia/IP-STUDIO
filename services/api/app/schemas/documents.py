from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.canvas import CanvasDocument


class DocumentSaveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_revision: int = Field(ge=0)
    document: CanvasDocument
    note: str | None = Field(default=None, max_length=500)


class DocumentRead(BaseModel):
    revision: int = Field(ge=0)
    document: CanvasDocument | None


class DocumentRevisionRead(BaseModel):
    revision_no: int
    note: str | None
    created_at: datetime


class DocumentRestoreRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_revision: int = Field(ge=0)


class DocumentRevisionSnapshotRead(DocumentRevisionRead):
    revision_id: UUID
    snapshot: CanvasDocument
