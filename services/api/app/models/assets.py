from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUID_COLUMN, new_id


class Asset(TimestampMixin, Base):
    __tablename__ = "assets"
    __table_args__ = (
        ForeignKeyConstraint(
            ["owner_ip_id", "workspace_id"],
            ["ips.id", "ips.workspace_id"],
            name="fk_assets_owner_ip_workspace",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "workspace_id", name="uq_assets_id_workspace"),
        CheckConstraint(
            "status IN ('candidate', 'approved', 'archived')", name="ck_assets_status"
        ),
        CheckConstraint(
            "type IN ('character_reference', 'character_pose', 'expression', 'scene', 'background', 'prop', 'composite_panel', 'texture', 'other')",
            name="ck_assets_type",
        ),
        CheckConstraint("source_type IN ('chatgpt_web', 'uploaded', 'edited_locally', 'other')", name="ck_assets_source_type"),
    )

    id: Mapped[UUID] = mapped_column(UUID_COLUMN, primary_key=True, default=new_id)
    workspace_id: Mapped[UUID] = mapped_column(
        UUID_COLUMN, ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False
    )
    owner_ip_id: Mapped[UUID | None] = mapped_column(UUID_COLUMN, nullable=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="candidate", server_default="candidate"
    )
    source_type: Mapped[str] = mapped_column(
        String(24), nullable=False, default="uploaded", server_default="uploaded"
    )
    rights_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class Blob(Base):
    __tablename__ = "blobs"
    __table_args__ = (
        UniqueConstraint("sha256", name="uq_blobs_sha256"),
        UniqueConstraint("storage_key", name="uq_blobs_storage_key"),
        CheckConstraint("byte_size > 0", name="ck_blobs_byte_size_positive"),
    )

    id: Mapped[UUID] = mapped_column(UUID_COLUMN, primary_key=True, default=new_id)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(96), nullable=False)
    mime: Mapped[str] = mapped_column(String(32), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)


class AssetVersion(TimestampMixin, Base):
    __tablename__ = "asset_versions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["asset_id", "workspace_id"],
            ["assets.id", "assets.workspace_id"],
            name="fk_asset_versions_asset_workspace",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(["blob_id"], ["blobs.id"], ondelete="RESTRICT"),
        UniqueConstraint("asset_id", "version_no", name="uq_asset_versions_asset_version"),
        UniqueConstraint("id", "workspace_id", name="uq_asset_versions_id_workspace"),
        CheckConstraint("version_no > 0", name="ck_asset_versions_version_positive"),
        CheckConstraint("width > 0 AND height > 0", name="ck_asset_versions_dimensions_positive"),
    )

    id: Mapped[UUID] = mapped_column(UUID_COLUMN, primary_key=True, default=new_id)
    workspace_id: Mapped[UUID] = mapped_column(UUID_COLUMN, nullable=False)
    asset_id: Mapped[UUID] = mapped_column(UUID_COLUMN, nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    blob_id: Mapped[UUID] = mapped_column(UUID_COLUMN, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    alpha: Mapped[bool] = mapped_column(nullable=False)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)


class AssetLink(Base):
    __tablename__ = "asset_links"
    __table_args__ = (
        ForeignKeyConstraint(
            ["asset_version_id"], ["asset_versions.id"], name="fk_asset_links_version", ondelete="RESTRICT"
        ),
    )

    id: Mapped[UUID] = mapped_column(UUID_COLUMN, primary_key=True, default=new_id)
    asset_version_id: Mapped[UUID] = mapped_column(UUID_COLUMN, nullable=False)
    owner_type: Mapped[str] = mapped_column(String(48), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[str] = mapped_column(String(48), nullable=False)
