"""Add immutable episode script revisions."""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_scripts"
down_revision: str | None = "0005_documents"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "script_revisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("episode_id", sa.Uuid(), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("source_markdown", sa.Text(), nullable=True),
        sa.Column("script_json", sa.JSON(), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["episode_id", "workspace_id"],
            ["episodes.id", "episodes.workspace_id"],
            name="fk_script_revisions_episode_workspace",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("episode_id", "revision_no", name="uq_script_revisions_episode_revision"),
        sa.UniqueConstraint("id", "workspace_id", name="uq_script_revisions_id_workspace"),
    )


def downgrade() -> None:
    op.drop_table("script_revisions")
