"""Add scoped assets, immutable versions, and content-addressed blobs."""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_assets"
down_revision: str | None = "0001_ip_story"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "assets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("owner_ip_id", sa.Uuid(), nullable=True),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=24), server_default="candidate", nullable=False),
        sa.Column("source_type", sa.String(length=24), server_default="uploaded", nullable=False),
        sa.Column("rights_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('candidate', 'approved', 'archived')", name="ck_assets_status"
        ),
        sa.CheckConstraint(
            "type IN ('character_reference', 'character_pose', 'expression', 'scene', 'background', 'prop', 'composite_panel', 'texture', 'other')",
            name="ck_assets_type",
        ),
        sa.CheckConstraint(
            "source_type IN ('chatgpt_web', 'uploaded', 'edited_locally', 'other')",
            name="ck_assets_source_type",
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["owner_ip_id", "workspace_id"],
            ["ips.id", "ips.workspace_id"],
            name="fk_assets_owner_ip_workspace",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "workspace_id", name="uq_assets_id_workspace"),
    )
    op.create_table(
        "blobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_key", sa.String(length=96), nullable=False),
        sa.Column("mime", sa.String(length=32), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.CheckConstraint("byte_size > 0", name="ck_blobs_byte_size_positive"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sha256", name="uq_blobs_sha256"),
        sa.UniqueConstraint("storage_key", name="uq_blobs_storage_key"),
    )
    op.create_table(
        "asset_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("blob_id", sa.Uuid(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("alpha", sa.Boolean(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("version_no > 0", name="ck_asset_versions_version_positive"),
        sa.CheckConstraint(
            "width > 0 AND height > 0", name="ck_asset_versions_dimensions_positive"
        ),
        sa.ForeignKeyConstraint(
            ["asset_id", "workspace_id"],
            ["assets.id", "assets.workspace_id"],
            name="fk_asset_versions_asset_workspace",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["blob_id"], ["blobs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("asset_id", "version_no", name="uq_asset_versions_asset_version"),
        sa.UniqueConstraint("id", "workspace_id", name="uq_asset_versions_id_workspace"),
    )
    op.create_table(
        "asset_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("asset_version_id", sa.Uuid(), nullable=False),
        sa.Column("owner_type", sa.String(length=48), nullable=False),
        sa.Column("owner_id", sa.String(length=128), nullable=False),
        sa.Column("role", sa.String(length=48), nullable=False),
        sa.ForeignKeyConstraint(
            ["asset_version_id"],
            ["asset_versions.id"],
            name="fk_asset_links_version",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("asset_links")
    op.drop_table("asset_versions")
    op.drop_table("blobs")
    op.drop_table("assets")
