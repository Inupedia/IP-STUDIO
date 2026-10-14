from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    JSON,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUID_COLUMN, new_id


class EpisodeDocument(TimestampMixin, Base):
    __tablename__ = "episode_documents"
    __table_args__ = (
        ForeignKeyConstraint(
            ["episode_id", "workspace_id"],
            ["episodes.id", "episodes.workspace_id"],
            name="fk_episode_documents_episode_workspace",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("episode_id", name="uq_episode_documents_episode"),
        UniqueConstraint("id", "workspace_id", name="uq_episode_documents_id_workspace"),
        UniqueConstraint(
            "id", "workspace_id", "episode_id", name="uq_episode_documents_id_workspace_episode"
        ),
        CheckConstraint("current_revision > 0", name="ck_episode_documents_revision_positive"),
    )

    id: Mapped[UUID] = mapped_column(UUID_COLUMN, primary_key=True, default=new_id)
    workspace_id: Mapped[UUID] = mapped_column(UUID_COLUMN, nullable=False)
    episode_id: Mapped[UUID] = mapped_column(UUID_COLUMN, nullable=False)
    current_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    document_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)


class DocumentRevision(Base):
    __tablename__ = "document_revisions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["episode_id", "workspace_id"],
            ["episodes.id", "episodes.workspace_id"],
            name="fk_document_revisions_episode_workspace",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "episode_id", "revision_no", name="uq_document_revisions_episode_revision"
        ),
        UniqueConstraint(
            "episode_id", "workspace_id", "revision_no",
            name="uq_document_revisions_episode_workspace_revision",
        ),
        CheckConstraint("revision_no > 0", name="ck_document_revisions_revision_positive"),
    )

    id: Mapped[UUID] = mapped_column(UUID_COLUMN, primary_key=True, default=new_id)
    workspace_id: Mapped[UUID] = mapped_column(UUID_COLUMN, nullable=False)
    episode_id: Mapped[UUID] = mapped_column(UUID_COLUMN, nullable=False)
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
