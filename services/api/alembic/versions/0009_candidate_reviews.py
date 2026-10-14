"""Record candidate review decisions and reviewer metadata."""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_candidate_reviews"
down_revision: str | None = "0008_generation_candidates"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("generation_candidates") as batch:
        batch.add_column(sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("reviewed_by_user_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("review_note", sa.Text(), nullable=True))
        batch.create_foreign_key(
            "fk_generation_candidates_reviewer_workspace",
            "users",
            ["reviewed_by_user_id", "workspace_id"],
            ["id", "workspace_id"],
            ondelete="RESTRICT",
        )
        batch.create_check_constraint(
            "ck_generation_candidates_review_metadata",
            "(status = 'pending_review' AND reviewed_at IS NULL AND reviewed_by_user_id IS NULL) "
            "OR (status IN ('approved', 'rejected') AND reviewed_at IS NOT NULL "
            "AND reviewed_by_user_id IS NOT NULL)",
        )


def downgrade() -> None:
    with op.batch_alter_table("generation_candidates") as batch:
        batch.drop_constraint("ck_generation_candidates_review_metadata", type_="check")
        batch.drop_constraint("fk_generation_candidates_reviewer_workspace", type_="foreignkey")
        batch.drop_column("review_note")
        batch.drop_column("reviewed_by_user_id")
        batch.drop_column("reviewed_at")
