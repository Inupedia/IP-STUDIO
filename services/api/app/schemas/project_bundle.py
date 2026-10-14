from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.canvas import CanvasDocument
from app.schemas.templates import BrandTemplateV1


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProjectSource(StrictModel):
    workspace_id: UUID
    ip_id: UUID
    ip_code: str = Field(min_length=1, max_length=32)
    ip_name: str = Field(min_length=1, max_length=120)
    series_id: UUID
    series_name: str = Field(min_length=1, max_length=120)
    series_summary: str | None
    episode_id: UUID
    episode_number: int = Field(gt=0)
    episode_title: str = Field(min_length=1, max_length=200)
    episode_status: str = Field(min_length=1, max_length=24)
    episode_default_style_version_id: UUID | None
    revision_no: int = Field(gt=0)


class ProjectAssetSnapshot(StrictModel):
    asset_id: UUID
    asset_version_id: UUID
    version_no: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=200)
    type: Literal[
        "character_reference", "character_pose", "expression", "scene", "background",
        "prop", "composite_panel", "texture", "other",
    ]
    source_type: Literal["chatgpt_web", "codex_native", "uploaded", "edited_locally", "other"]
    rights_note: str | None
    status: Literal["approved"]
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    alpha: bool
    metadata_json: dict[str, object]
    approved_at: datetime
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    mime: Literal["image/png", "image/jpeg", "image/webp"]
    byte_size: int = Field(gt=0)
    blob_path: str = Field(min_length=1)

    @model_validator(mode="after")
    def blob_path_matches_digest(self) -> "ProjectAssetSnapshot":
        extension = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}[self.mime]
        if self.blob_path != f"blobs/{self.sha256}.{extension}":
            raise ValueError("Blob path must match the content hash and MIME type")
        return self


class ProjectStyleSnapshot(StrictModel):
    style_id: UUID
    style_name: str = Field(min_length=1, max_length=120)
    version_id: UUID
    version_no: int = Field(gt=0)
    approved_at: datetime
    bible_json: dict[str, object]


class ProjectBrandSnapshot(StrictModel):
    template_id: UUID
    template_name: str = Field(min_length=1, max_length=120)
    version_id: UUID
    version_no: int = Field(gt=0)
    approved_at: datetime
    template_json: BrandTemplateV1


class ProjectManifest(StrictModel):
    schema_version: Literal["1.0"]
    exported_at: datetime
    source: ProjectSource
    brand: ProjectBrandSnapshot
    styles: list[ProjectStyleSnapshot]
    assets: list[ProjectAssetSnapshot]

    @model_validator(mode="after")
    def has_unique_versions(self) -> "ProjectManifest":
        asset_ids = [asset.asset_version_id for asset in self.assets]
        style_ids = [style.version_id for style in self.styles]
        if len(set(asset_ids)) != len(asset_ids):
            raise ValueError("Asset version IDs must be unique")
        if len(set(style_ids)) != len(style_ids):
            raise ValueError("Style version IDs must be unique")
        assets_by_id: dict[UUID, list[ProjectAssetSnapshot]] = {}
        for asset in self.assets:
            assets_by_id.setdefault(asset.asset_id, []).append(asset)
        for versions in assets_by_id.values():
            static_metadata = {
                (item.name, item.type, item.source_type, item.rights_note) for item in versions
            }
            version_numbers = [item.version_no for item in versions]
            if len(static_metadata) != 1 or len(set(version_numbers)) != len(version_numbers):
                raise ValueError("Asset versions must share metadata and use unique version numbers")

        styles_by_id: dict[UUID, list[ProjectStyleSnapshot]] = {}
        for style in self.styles:
            styles_by_id.setdefault(style.style_id, []).append(style)
        for versions in styles_by_id.values():
            version_numbers = [item.version_no for item in versions]
            if (
                len({item.style_name for item in versions}) != 1
                or len(set(version_numbers)) != len(version_numbers)
            ):
                raise ValueError("Style versions must share a name and use unique version numbers")
        return self


class ProjectBundleExportRequest(StrictModel):
    revision_no: int = Field(gt=0)


class ProjectBundleImportRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ip_id: UUID
    series_id: UUID
    episode_id: UUID
    revision_no: int = Field(gt=0)
    brand_template_version_id: UUID
    style_version_id: UUID | None
    asset_version_id_map: dict[UUID, UUID]
