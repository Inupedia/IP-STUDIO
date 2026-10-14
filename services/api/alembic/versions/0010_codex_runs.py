"""Add local Codex ImageGen run tracking."""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_codex_runs"
down_revision: str | None = "0009_candidate_reviews"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("assets") as batch:
        batch.drop_constraint("ck_assets_source_type", type_="check")
        batch.create_check_constraint(
            "ck_assets_source_type",
            "source_type IN ('chatgpt_web', 'codex_native', 'uploaded', 'edited_locally', 'other')",
        )

    with op.batch_alter_table("generation_candidates") as batch:
        batch.create_unique_constraint(
            "uq_generation_candidates_id_workspace_task", ["id", "workspace_id", "task_id"]
        )

    op.create_table(
        "codex_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_reason", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'candidate_ready', 'failed')",
            name="ck_codex_runs_status",
        ),
        sa.CheckConstraint(
            "(status = 'queued' AND started_at IS NULL AND completed_at IS NULL AND candidate_id IS NULL) "
            "OR (status = 'running' AND started_at IS NOT NULL AND completed_at IS NULL AND candidate_id IS NULL) "
            "OR (status = 'candidate_ready' AND started_at IS NOT NULL AND completed_at IS NOT NULL AND candidate_id IS NOT NULL) "
            "OR (status = 'failed' AND started_at IS NOT NULL AND completed_at IS NOT NULL AND candidate_id IS NULL)",
            name="ck_codex_runs_state_shape",
        ),
        sa.ForeignKeyConstraint(
            ["task_id", "workspace_id"],
            ["generation_tasks.id", "generation_tasks.workspace_id"],
            name="fk_codex_runs_task_workspace",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id", "workspace_id", "task_id"],
            ["generation_candidates.id", "generation_candidates.workspace_id", "generation_candidates.task_id"],
            name="fk_codex_runs_candidate_workspace_task",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("candidate_id", name="uq_codex_runs_candidate"),
    )
    op.create_index(
        "uq_codex_runs_active_task",
        "codex_runs",
        ["workspace_id", "task_id"],
        unique=True,
        sqlite_where=sa.text("status IN ('queued', 'running')"),
        postgresql_where=sa.text("status IN ('queued', 'running')"),
    )


def downgrade() -> None:
    op.drop_index("uq_codex_runs_active_task", table_name="codex_runs")
    op.drop_table("codex_runs")
    with op.batch_alter_table("generation_candidates") as batch:
        batch.drop_constraint("uq_generation_candidates_id_workspace_task", type_="unique")
    with op.batch_alter_table("assets") as batch:
        batch.drop_constraint("ck_assets_source_type", type_="check")
        batch.create_check_constraint(
            "ck_assets_source_type",
            "source_type IN ('chatgpt_web', 'uploaded', 'edited_locally', 'other')",
        )
