"""Persist scoped Codex patch proposals and review decisions."""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_codex_patch_approvals"
down_revision: str | None = "0010_codex_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("episode_documents") as batch:
        batch.create_unique_constraint(
            "uq_episode_documents_id_workspace_episode", ["id", "workspace_id", "episode_id"]
        )

    op.create_table(
        "codex_patch_proposals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("approval_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("ip_id", sa.Uuid(), nullable=False),
        sa.Column("episode_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("base_revision", sa.Integer(), nullable=False),
        sa.Column("patch_json", sa.JSON(), nullable=False),
        sa.Column("preview_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("reviewed_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("applied_revision", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending_approval', 'approved', 'rejected')",
            name="ck_codex_patch_proposals_status",
        ),
        sa.CheckConstraint("base_revision >= 0", name="ck_codex_patch_proposals_base_revision"),
        sa.CheckConstraint(
            "(status = 'pending_approval' AND reviewed_at IS NULL AND reviewed_by_user_id IS NULL AND applied_revision IS NULL) "
            "OR (status = 'approved' AND reviewed_at IS NOT NULL AND reviewed_by_user_id IS NOT NULL AND applied_revision = base_revision + 1) "
            "OR (status = 'rejected' AND reviewed_at IS NOT NULL AND reviewed_by_user_id IS NOT NULL AND applied_revision IS NULL)",
            name="ck_codex_patch_proposals_review_state",
        ),
        sa.ForeignKeyConstraint(
            ["ip_id", "workspace_id"], ["ips.id", "ips.workspace_id"],
            name="fk_codex_patch_proposals_ip_workspace", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["episode_id", "workspace_id"], ["episodes.id", "episodes.workspace_id"],
            name="fk_codex_patch_proposals_episode_workspace", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["document_id", "workspace_id", "episode_id"],
            ["episode_documents.id", "episode_documents.workspace_id", "episode_documents.episode_id"],
            name="fk_codex_patch_proposals_document_scope", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id", "workspace_id"], ["users.id", "users.workspace_id"],
            name="fk_codex_patch_proposals_creator_workspace", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by_user_id", "workspace_id"], ["users.id", "users.workspace_id"],
            name="fk_codex_patch_proposals_reviewer_workspace", ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("approval_id", name="uq_codex_patch_proposals_approval_id"),
        sa.UniqueConstraint("id", "workspace_id", name="uq_codex_patch_proposals_id_workspace"),
    )


def downgrade() -> None:
    op.drop_table("codex_patch_proposals")
    with op.batch_alter_table("episode_documents") as batch:
        batch.drop_constraint("uq_episode_documents_id_workspace_episode", type_="unique")
