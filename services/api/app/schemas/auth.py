from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TokenRead(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"


class AdminRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    email: str
    is_admin: bool
