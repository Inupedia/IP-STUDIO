from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUID_COLUMN, new_id


class GenerationCandidate(TimestampMixin, Base):
    __tablename__ = "generation_candidates"
    __table_args__ = (
        ForeignKeyConstraint(
            ["task_id", "workspace_id"],
            ["generation_tasks.id", "generation_tasks.workspace_id"],
            name="fk_generation_candidates_task_workspace",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["asset_version_id", "workspace_id"],
            ["asset_versions.id", "asset_versions.workspace_id"],
            name="fk_generation_candidates_asset_workspace",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("asset_version_id", name="uq_generation_candidates_asset_version"),
        UniqueConstraint("id", "workspace_id", name="uq_generation_candidates_id_workspace"),
        CheckConstraint(
            "status IN ('pending_review', 'approved', 'rejected')",
            name="ck_generation_candidates_status",
        ),
        CheckConstraint(
            "(status = 'pending_review' AND reviewed_at IS NULL AND reviewed_by_user_id IS NULL) "
            "OR (status IN ('approved', 'rejected') AND reviewed_at IS NOT NULL "
            "AND reviewed_by_user_id IS NOT NULL)",
            name="ck_generation_candidates_review_metadata",
        ),
        ForeignKeyConstraint(
            ["reviewed_by_user_id", "workspace_id"],
            ["users.id", "users.workspace_id"],
            name="fk_generation_candidates_reviewer_workspace",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[UUID] = mapped_column(UUID_COLUMN, primary_key=True, default=new_id)
    workspace_id: Mapped[UUID] = mapped_column(UUID_COLUMN, nullable=False)
    task_id: Mapped[UUID] = mapped_column(UUID_COLUMN, nullable=False)
    panel_id: Mapped[UUID] = mapped_column(UUID_COLUMN, nullable=False)
    asset_version_id: Mapped[UUID] = mapped_column(UUID_COLUMN, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending_review")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by_user_id: Mapped[UUID | None] = mapped_column(UUID_COLUMN, nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
