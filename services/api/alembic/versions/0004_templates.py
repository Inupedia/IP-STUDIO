"""Add immutable, IP-scoped brand templates."""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_templates"
down_revision: str | None = "0003_bibles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "brand_templates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("ip_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["ip_id", "workspace_id"],
            ["ips.id", "ips.workspace_id"],
            name="fk_brand_templates_ip_workspace",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "workspace_id", name="uq_brand_templates_id_workspace"),
    )
    op.create_table(
        "brand_template_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("brand_template_id", sa.Uuid(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("template_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=24), server_default="candidate", nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("derived_from_version_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("version_no > 0", name="ck_brand_template_versions_version_positive"),
        sa.CheckConstraint(
            "status IN ('candidate', 'approved', 'archived')",
            name="ck_brand_template_versions_status",
        ),
        sa.ForeignKeyConstraint(
            ["brand_template_id", "workspace_id"],
            ["brand_templates.id", "brand_templates.workspace_id"],
            name="fk_brand_template_versions_template_workspace",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["approved_by_user_id", "workspace_id"],
            ["users.id", "users.workspace_id"],
            name="fk_brand_template_versions_approver_workspace",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["derived_from_version_id", "brand_template_id"],
            ["brand_template_versions.id", "brand_template_versions.brand_template_id"],
            name="fk_brand_template_versions_parent_template",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "brand_template_id", "version_no", name="uq_brand_template_versions_template_version"
        ),
        sa.UniqueConstraint("id", "workspace_id", name="uq_brand_template_versions_id_workspace"),
        sa.UniqueConstraint(
            "id", "brand_template_id", name="uq_brand_template_versions_id_template"
        ),
    )


def downgrade() -> None:
    op.drop_table("brand_template_versions")
    op.drop_table("brand_templates")
