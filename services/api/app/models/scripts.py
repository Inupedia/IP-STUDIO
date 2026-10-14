from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKeyConstraint, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUID_COLUMN, new_id


class ScriptRevision(Base):
    __tablename__ = "script_revisions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["episode_id", "workspace_id"],
            ["episodes.id", "episodes.workspace_id"],
            name="fk_script_revisions_episode_workspace",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("episode_id", "revision_no", name="uq_script_revisions_episode_revision"),
        UniqueConstraint("id", "workspace_id", name="uq_script_revisions_id_workspace"),
    )

    id: Mapped[UUID] = mapped_column(UUID_COLUMN, primary_key=True, default=new_id)
    workspace_id: Mapped[UUID] = mapped_column(UUID_COLUMN, nullable=False)
    episode_id: Mapped[UUID] = mapped_column(UUID_COLUMN, nullable=False)
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
    source_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    script_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
