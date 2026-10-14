from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKeyConstraint, Index, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUID_COLUMN, new_id


class CodexRun(TimestampMixin, Base):
    __tablename__ = "codex_runs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["task_id", "workspace_id"],
            ["generation_tasks.id", "generation_tasks.workspace_id"],
            name="fk_codex_runs_task_workspace",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["candidate_id", "workspace_id", "task_id"],
            [
                "generation_candidates.id",
                "generation_candidates.workspace_id",
                "generation_candidates.task_id",
            ],
            name="fk_codex_runs_candidate_workspace_task",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("candidate_id", name="uq_codex_runs_candidate"),
        Index(
            "uq_codex_runs_active_task",
            "workspace_id",
            "task_id",
            unique=True,
            sqlite_where=text("status IN ('queued', 'running')"),
            postgresql_where=text("status IN ('queued', 'running')"),
        ),
        CheckConstraint(
            "status IN ('queued', 'running', 'candidate_ready', 'failed')",
            name="ck_codex_runs_status",
        ),
        CheckConstraint(
            "(status = 'queued' AND started_at IS NULL AND completed_at IS NULL AND candidate_id IS NULL) "
            "OR (status = 'running' AND started_at IS NOT NULL AND completed_at IS NULL AND candidate_id IS NULL) "
            "OR (status = 'candidate_ready' AND started_at IS NOT NULL AND completed_at IS NOT NULL AND candidate_id IS NOT NULL) "
            "OR (status = 'failed' AND started_at IS NOT NULL AND completed_at IS NOT NULL AND candidate_id IS NULL)",
            name="ck_codex_runs_state_shape",
        ),
    )

    id: Mapped[UUID] = mapped_column(UUID_COLUMN, primary_key=True, default=new_id)
    workspace_id: Mapped[UUID] = mapped_column(UUID_COLUMN, nullable=False)
    task_id: Mapped[UUID] = mapped_column(UUID_COLUMN, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="queued")
    candidate_id: Mapped[UUID | None] = mapped_column(UUID_COLUMN, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
