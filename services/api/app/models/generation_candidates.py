from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, String, UniqueConstraint
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
    )

    id: Mapped[UUID] = mapped_column(UUID_COLUMN, primary_key=True, default=new_id)
    workspace_id: Mapped[UUID] = mapped_column(UUID_COLUMN, nullable=False)
    task_id: Mapped[UUID] = mapped_column(UUID_COLUMN, nullable=False)
    panel_id: Mapped[UUID] = mapped_column(UUID_COLUMN, nullable=False)
    asset_version_id: Mapped[UUID] = mapped_column(UUID_COLUMN, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending_review")
