"""Add immutable character/style Bibles and approval metadata."""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_bibles"
down_revision: str | None = "0002_assets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.create_unique_constraint("uq_users_id_workspace", ["id", "workspace_id"])

    with op.batch_alter_table("asset_versions") as batch_op:
        batch_op.add_column(
            sa.Column("status", sa.String(length=24), server_default="candidate", nullable=False)
        )
        batch_op.add_column(sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("approved_by_user_id", sa.Uuid(), nullable=True))
        batch_op.create_check_constraint(
            "ck_asset_versions_status", "status IN ('candidate', 'approved', 'archived')"
        )
        batch_op.create_foreign_key(
            "fk_asset_versions_approver_workspace",
            "users",
            ["approved_by_user_id", "workspace_id"],
            ["id", "workspace_id"],
            ondelete="RESTRICT",
        )

    op.create_table(
        "characters",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("ip_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=48), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["ip_id", "workspace_id"],
            ["ips.id", "ips.workspace_id"],
            name="fk_characters_ip_workspace",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "workspace_id", name="uq_characters_id_workspace"),
        sa.UniqueConstraint("ip_id", "code", name="uq_characters_ip_code"),
    )
    op.create_table(
        "character_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("character_id", sa.Uuid(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("bible_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=24), server_default="candidate", nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("derived_from_version_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("version_no > 0", name="ck_character_versions_version_positive"),
        sa.CheckConstraint(
            "status IN ('candidate', 'approved', 'archived')", name="ck_character_versions_status"
        ),
        sa.ForeignKeyConstraint(
            ["character_id", "workspace_id"],
            ["characters.id", "characters.workspace_id"],
            name="fk_character_versions_character_workspace",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["approved_by_user_id", "workspace_id"],
            ["users.id", "users.workspace_id"],
            name="fk_character_versions_approver_workspace",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["derived_from_version_id", "character_id"],
            ["character_versions.id", "character_versions.character_id"],
            name="fk_character_versions_parent_character",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("character_id", "version_no", name="uq_character_versions_character_version"),
        sa.UniqueConstraint("id", "workspace_id", name="uq_character_versions_id_workspace"),
        sa.UniqueConstraint("id", "character_id", name="uq_character_versions_id_character"),
    )
    op.create_table(
        "styles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("ip_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["ip_id", "workspace_id"],
            ["ips.id", "ips.workspace_id"],
            name="fk_styles_ip_workspace",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "workspace_id", name="uq_styles_id_workspace"),
    )
    op.create_table(
        "style_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("style_id", sa.Uuid(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("bible_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=24), server_default="candidate", nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("derived_from_version_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("version_no > 0", name="ck_style_versions_version_positive"),
        sa.CheckConstraint("status IN ('candidate', 'approved', 'archived')", name="ck_style_versions_status"),
        sa.ForeignKeyConstraint(
            ["style_id", "workspace_id"],
            ["styles.id", "styles.workspace_id"],
            name="fk_style_versions_style_workspace",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["approved_by_user_id", "workspace_id"],
            ["users.id", "users.workspace_id"],
            name="fk_style_versions_approver_workspace",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["derived_from_version_id", "style_id"],
            ["style_versions.id", "style_versions.style_id"],
            name="fk_style_versions_parent_style",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("style_id", "version_no", name="uq_style_versions_style_version"),
        sa.UniqueConstraint("id", "workspace_id", name="uq_style_versions_id_workspace"),
        sa.UniqueConstraint("id", "style_id", name="uq_style_versions_id_style"),
    )
    with op.batch_alter_table("ips") as batch_op:
        batch_op.add_column(sa.Column("default_style_version_id", sa.Uuid(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("ips") as batch_op:
        batch_op.drop_column("default_style_version_id")
    op.drop_table("style_versions")
    op.drop_table("styles")
    op.drop_table("character_versions")
    op.drop_table("characters")
    with op.batch_alter_table("asset_versions") as batch_op:
        batch_op.drop_constraint("fk_asset_versions_approver_workspace", type_="foreignkey")
        batch_op.drop_constraint("ck_asset_versions_status", type_="check")
        batch_op.drop_column("approved_by_user_id")
        batch_op.drop_column("approved_at")
        batch_op.drop_column("status")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("uq_users_id_workspace", type_="unique")
