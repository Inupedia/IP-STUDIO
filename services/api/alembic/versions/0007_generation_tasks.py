"""Add immutable manual generation task snapshots."""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_generation_tasks"
down_revision: str | None = "0006_scripts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "generation_tasks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("episode_id", sa.Uuid(), nullable=False),
        sa.Column("script_revision_id", sa.Uuid(), nullable=False),
        sa.Column("script_revision_no", sa.Integer(), nullable=False),
        sa.Column("panel_id", sa.Uuid(), nullable=False),
        sa.Column("mode", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("prompt_snapshot", sa.JSON(), nullable=False),
        sa.Column("reference_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("script_revision_no > 0", name="ck_generation_tasks_script_revision_positive"),
        sa.CheckConstraint("mode IN ('chatgpt_web')", name="ck_generation_tasks_mode"),
        sa.CheckConstraint(
            "status IN ('prepared', 'waiting_manual_generation', 'asset_imported')",
            name="ck_generation_tasks_status",
        ),
        sa.ForeignKeyConstraint(
            ["episode_id", "workspace_id"],
            ["episodes.id", "episodes.workspace_id"],
            name="fk_generation_tasks_episode_workspace",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["script_revision_id", "workspace_id"],
            ["script_revisions.id", "script_revisions.workspace_id"],
            name="fk_generation_tasks_script_revision_workspace",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "workspace_id", name="uq_generation_tasks_id_workspace"),
    )


def downgrade() -> None:
    op.drop_table("generation_tasks")
