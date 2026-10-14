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


class BrandTemplate(TimestampMixin, Base):
    __tablename__ = "brand_templates"
    __table_args__ = (
        ForeignKeyConstraint(
            ["ip_id", "workspace_id"],
            ["ips.id", "ips.workspace_id"],
            name="fk_brand_templates_ip_workspace",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "workspace_id", name="uq_brand_templates_id_workspace"),
    )

    id: Mapped[UUID] = mapped_column(UUID_COLUMN, primary_key=True, default=new_id)
    workspace_id: Mapped[UUID] = mapped_column(UUID_COLUMN, nullable=False)
    ip_id: Mapped[UUID] = mapped_column(UUID_COLUMN, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)


class BrandTemplateVersion(TimestampMixin, Base):
    __tablename__ = "brand_template_versions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["brand_template_id", "workspace_id"],
            ["brand_templates.id", "brand_templates.workspace_id"],
            name="fk_brand_template_versions_template_workspace",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["approved_by_user_id", "workspace_id"],
            ["users.id", "users.workspace_id"],
            name="fk_brand_template_versions_approver_workspace",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["derived_from_version_id", "brand_template_id"],
            ["brand_template_versions.id", "brand_template_versions.brand_template_id"],
            name="fk_brand_template_versions_parent_template",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "brand_template_id", "version_no", name="uq_brand_template_versions_template_version"
        ),
        UniqueConstraint("id", "workspace_id", name="uq_brand_template_versions_id_workspace"),
        UniqueConstraint(
            "id", "brand_template_id", name="uq_brand_template_versions_id_template"
        ),
        CheckConstraint("version_no > 0", name="ck_brand_template_versions_version_positive"),
        CheckConstraint(
            "status IN ('candidate', 'approved', 'archived')",
            name="ck_brand_template_versions_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(UUID_COLUMN, primary_key=True, default=new_id)
    workspace_id: Mapped[UUID] = mapped_column(UUID_COLUMN, nullable=False)
    brand_template_id: Mapped[UUID] = mapped_column(UUID_COLUMN, nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    template_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="candidate", server_default="candidate"
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by_user_id: Mapped[UUID | None] = mapped_column(UUID_COLUMN, nullable=True)
    derived_from_version_id: Mapped[UUID | None] = mapped_column(UUID_COLUMN, nullable=True)
