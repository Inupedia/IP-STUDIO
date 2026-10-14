from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AssetType(str, Enum):
    CHARACTER_REFERENCE = "character_reference"
    CHARACTER_POSE = "character_pose"
    EXPRESSION = "expression"
    SCENE = "scene"
    BACKGROUND = "background"
    PROP = "prop"
    COMPOSITE_PANEL = "composite_panel"
    TEXTURE = "texture"
    OTHER = "other"


class AssetStatus(str, Enum):
    CANDIDATE = "candidate"
    APPROVED = "approved"
    ARCHIVED = "archived"


class AssetSourceType(str, Enum):
    CHATGPT_WEB = "chatgpt_web"
    CODEX_NATIVE = "codex_native"
    UPLOADED = "uploaded"
    EDITED_LOCALLY = "edited_locally"
    OTHER = "other"


class AssetUploadRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    asset_id: UUID
    asset_version_id: UUID
    workspace_id: UUID
    owner_ip_id: UUID
    type: AssetType
    name: str
    status: AssetStatus
    source_type: AssetSourceType
    version_no: int
    sha256: str
    mime: str
    byte_size: int
    width: int
    height: int
    alpha: bool
    created_at: datetime
