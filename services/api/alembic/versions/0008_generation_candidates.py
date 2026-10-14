"""Add task-bound generation candidates."""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_generation_candidates"
down_revision: str | None = "0007_generation_tasks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "generation_candidates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("panel_id", sa.Uuid(), nullable=False),
        sa.Column("asset_version_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending_review', 'approved', 'rejected')",
            name="ck_generation_candidates_status",
        ),
        sa.ForeignKeyConstraint(
            ["task_id", "workspace_id"],
            ["generation_tasks.id", "generation_tasks.workspace_id"],
            name="fk_generation_candidates_task_workspace",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["asset_version_id", "workspace_id"],
            ["asset_versions.id", "asset_versions.workspace_id"],
            name="fk_generation_candidates_asset_workspace",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("asset_version_id", name="uq_generation_candidates_asset_version"),
        sa.UniqueConstraint("id", "workspace_id", name="uq_generation_candidates_id_workspace"),
    )


def downgrade() -> None:
    op.drop_table("generation_candidates")
