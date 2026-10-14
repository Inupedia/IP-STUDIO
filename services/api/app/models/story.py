from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, ForeignKeyConstraint, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUID_COLUMN, new_id


class Series(TimestampMixin, Base):
    __tablename__ = "series"
    __table_args__ = (
        ForeignKeyConstraint(
            ["ip_id", "workspace_id"],
            ["ips.id", "ips.workspace_id"],
            name="fk_series_ip_workspace",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "workspace_id", name="uq_series_id_workspace"),
    )

    id: Mapped[UUID] = mapped_column(UUID_COLUMN, primary_key=True, default=new_id)
    workspace_id: Mapped[UUID] = mapped_column(
        UUID_COLUMN, ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False
    )
    ip_id: Mapped[UUID] = mapped_column(UUID_COLUMN, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)


class Episode(TimestampMixin, Base):
    __tablename__ = "episodes"
    __table_args__ = (
        ForeignKeyConstraint(
            ["series_id", "workspace_id"],
            ["series.id", "series.workspace_id"],
            name="fk_episodes_series_workspace",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("series_id", "number", name="uq_episodes_series_number"),
        UniqueConstraint("id", "workspace_id", name="uq_episodes_id_workspace"),
        CheckConstraint("number > 0", name="ck_episodes_number_positive"),
    )

    id: Mapped[UUID] = mapped_column(UUID_COLUMN, primary_key=True, default=new_id)
    workspace_id: Mapped[UUID] = mapped_column(
        UUID_COLUMN, ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False
    )
    series_id: Mapped[UUID] = mapped_column(UUID_COLUMN, nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft")
    default_style_version_id: Mapped[UUID | None] = mapped_column(UUID_COLUMN, nullable=True)
