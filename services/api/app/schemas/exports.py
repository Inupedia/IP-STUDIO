from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ExportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    episode_id: UUID
    revision_no: int
    format: Literal["png_zip", "project_zip", "pptx"]
    status: Literal["complete", "failed"]
    page_count: int = Field(gt=0)
    warnings: list[str]
    download_url: str | None
    created_at: datetime
