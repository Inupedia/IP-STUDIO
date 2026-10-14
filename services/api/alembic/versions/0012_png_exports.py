"""Persist PNG page-group export artifacts tied to exact revisions."""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_png_exports"
down_revision: str | None = "0011_codex_patch_approvals"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("document_revisions") as batch:
        batch.create_unique_constraint(
            "uq_document_revisions_episode_workspace_revision",
            ["episode_id", "workspace_id", "revision_no"],
        )

    op.create_table(
        "export_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("episode_id", sa.Uuid(), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("format", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("file_blob_id", sa.Uuid(), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("warnings_json", sa.JSON(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("revision_no > 0", name="ck_export_jobs_revision_positive"),
        sa.CheckConstraint("page_count > 0", name="ck_export_jobs_page_count_positive"),
        sa.CheckConstraint("format IN ('png_zip', 'project_zip', 'pptx')", name="ck_export_jobs_format"),
        sa.CheckConstraint("status IN ('complete', 'failed')", name="ck_export_jobs_status"),
        sa.CheckConstraint(
            "(status = 'complete' AND file_blob_id IS NOT NULL) OR (status = 'failed' AND file_blob_id IS NULL)",
            name="ck_export_jobs_result_state",
        ),
        sa.ForeignKeyConstraint(
            ["episode_id", "workspace_id"], ["episodes.id", "episodes.workspace_id"],
            name="fk_export_jobs_episode_workspace", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["episode_id", "workspace_id", "revision_no"],
            ["document_revisions.episode_id", "document_revisions.workspace_id", "document_revisions.revision_no"],
            name="fk_export_jobs_revision_scope", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["file_blob_id"], ["blobs.id"], name="fk_export_jobs_blob", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["created_by_user_id", "workspace_id"], ["users.id", "users.workspace_id"],
            name="fk_export_jobs_creator_workspace", ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "workspace_id", name="uq_export_jobs_id_workspace"),
    )


def downgrade() -> None:
    op.drop_table("export_jobs")
    with op.batch_alter_table("document_revisions") as batch:
        batch.drop_constraint("uq_document_revisions_episode_workspace_revision", type_="unique")
