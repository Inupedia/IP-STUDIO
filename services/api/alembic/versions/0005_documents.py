"""Add atomic episode documents and immutable revision snapshots."""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_documents"
down_revision: str | None = "0004_templates"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "episode_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("episode_id", sa.Uuid(), nullable=False),
        sa.Column("current_revision", sa.Integer(), nullable=False),
        sa.Column("document_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("current_revision > 0", name="ck_episode_documents_revision_positive"),
        sa.ForeignKeyConstraint(
            ["episode_id", "workspace_id"],
            ["episodes.id", "episodes.workspace_id"],
            name="fk_episode_documents_episode_workspace",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("episode_id", name="uq_episode_documents_episode"),
        sa.UniqueConstraint("id", "workspace_id", name="uq_episode_documents_id_workspace"),
    )
    op.create_table(
        "document_revisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("episode_id", sa.Uuid(), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("snapshot_json", sa.JSON(), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("revision_no > 0", name="ck_document_revisions_revision_positive"),
        sa.ForeignKeyConstraint(
            ["episode_id", "workspace_id"],
            ["episodes.id", "episodes.workspace_id"],
            name="fk_document_revisions_episode_workspace",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "episode_id", "revision_no", name="uq_document_revisions_episode_revision"
        ),
    )


def downgrade() -> None:
    op.drop_table("document_revisions")
    op.drop_table("episode_documents")
