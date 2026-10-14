from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKeyConstraint,
    Integer,
    JSON,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUID_COLUMN, new_id


class GenerationTask(TimestampMixin, Base):
    __tablename__ = "generation_tasks"
    __table_args__ = (
        ForeignKeyConstraint(
            ["episode_id", "workspace_id"],
            ["episodes.id", "episodes.workspace_id"],
            name="fk_generation_tasks_episode_workspace",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["script_revision_id", "workspace_id"],
            ["script_revisions.id", "script_revisions.workspace_id"],
            name="fk_generation_tasks_script_revision_workspace",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "workspace_id", name="uq_generation_tasks_id_workspace"),
        CheckConstraint("script_revision_no > 0", name="ck_generation_tasks_script_revision_positive"),
        CheckConstraint("mode IN ('chatgpt_web')", name="ck_generation_tasks_mode"),
        CheckConstraint(
            "status IN ('prepared', 'waiting_manual_generation', 'asset_imported')",
            name="ck_generation_tasks_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(UUID_COLUMN, primary_key=True, default=new_id)
    workspace_id: Mapped[UUID] = mapped_column(UUID_COLUMN, nullable=False)
    episode_id: Mapped[UUID] = mapped_column(UUID_COLUMN, nullable=False)
    script_revision_id: Mapped[UUID] = mapped_column(UUID_COLUMN, nullable=False)
    script_revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
    panel_id: Mapped[UUID] = mapped_column(UUID_COLUMN, nullable=False)
    mode: Mapped[str] = mapped_column(String(24), nullable=False, default="chatgpt_web")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="prepared")
    prompt_snapshot: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    reference_snapshot: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
