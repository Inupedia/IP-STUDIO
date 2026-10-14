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


class ExportJob(TimestampMixin, Base):
    __tablename__ = "export_jobs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["episode_id", "workspace_id"],
            ["episodes.id", "episodes.workspace_id"],
            name="fk_export_jobs_episode_workspace",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["episode_id", "workspace_id", "revision_no"],
            ["document_revisions.episode_id", "document_revisions.workspace_id", "document_revisions.revision_no"],
            name="fk_export_jobs_revision_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(["file_blob_id"], ["blobs.id"], name="fk_export_jobs_blob", ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["created_by_user_id", "workspace_id"],
            ["users.id", "users.workspace_id"],
            name="fk_export_jobs_creator_workspace",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "workspace_id", name="uq_export_jobs_id_workspace"),
        CheckConstraint("revision_no > 0", name="ck_export_jobs_revision_positive"),
        CheckConstraint("page_count > 0", name="ck_export_jobs_page_count_positive"),
        CheckConstraint("format IN ('png_zip', 'project_zip', 'pptx')", name="ck_export_jobs_format"),
        CheckConstraint("status IN ('complete', 'failed')", name="ck_export_jobs_status"),
        CheckConstraint(
            "(status = 'complete' AND file_blob_id IS NOT NULL) OR (status = 'failed' AND file_blob_id IS NULL)",
            name="ck_export_jobs_result_state",
        ),
    )

    id: Mapped[UUID] = mapped_column(UUID_COLUMN, primary_key=True, default=new_id)
    workspace_id: Mapped[UUID] = mapped_column(UUID_COLUMN, nullable=False)
    episode_id: Mapped[UUID] = mapped_column(UUID_COLUMN, nullable=False)
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
    format: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="complete")
    file_blob_id: Mapped[UUID | None] = mapped_column(UUID_COLUMN, nullable=True)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False)
    warnings_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_by_user_id: Mapped[UUID] = mapped_column(UUID_COLUMN, nullable=False)
