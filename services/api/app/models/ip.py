from uuid import UUID

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUID_COLUMN, new_id


class IP(TimestampMixin, Base):
    __tablename__ = "ips"
    __table_args__ = (
        UniqueConstraint("workspace_id", "code", name="uq_ips_workspace_code"),
        UniqueConstraint("id", "workspace_id", name="uq_ips_id_workspace"),
    )

    id: Mapped[UUID] = mapped_column(UUID_COLUMN, primary_key=True, default=new_id)
    workspace_id: Mapped[UUID] = mapped_column(
        UUID_COLUMN, ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")
