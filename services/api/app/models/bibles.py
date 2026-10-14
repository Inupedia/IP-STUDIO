from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    JSON,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUID_COLUMN, new_id


class Character(TimestampMixin, Base):
    __tablename__ = "characters"
    __table_args__ = (
        ForeignKeyConstraint(
            ["ip_id", "workspace_id"],
            ["ips.id", "ips.workspace_id"],
            name="fk_characters_ip_workspace",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("ip_id", "code", name="uq_characters_ip_code"),
        UniqueConstraint("id", "workspace_id", name="uq_characters_id_workspace"),
    )

    id: Mapped[UUID] = mapped_column(UUID_COLUMN, primary_key=True, default=new_id)
    workspace_id: Mapped[UUID] = mapped_column(UUID_COLUMN, nullable=False)
    ip_id: Mapped[UUID] = mapped_column(UUID_COLUMN, nullable=False)
    code: Mapped[str] = mapped_column(String(48), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)


class CharacterVersion(TimestampMixin, Base):
    __tablename__ = "character_versions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["character_id", "workspace_id"],
            ["characters.id", "characters.workspace_id"],
            name="fk_character_versions_character_workspace",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["approved_by_user_id", "workspace_id"],
            ["users.id", "users.workspace_id"],
            name="fk_character_versions_approver_workspace",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["derived_from_version_id", "character_id"],
            ["character_versions.id", "character_versions.character_id"],
            name="fk_character_versions_parent_character",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("character_id", "version_no", name="uq_character_versions_character_version"),
        UniqueConstraint("id", "workspace_id", name="uq_character_versions_id_workspace"),
        UniqueConstraint("id", "character_id", name="uq_character_versions_id_character"),
        CheckConstraint("version_no > 0", name="ck_character_versions_version_positive"),
        CheckConstraint(
            "status IN ('candidate', 'approved', 'archived')", name="ck_character_versions_status"
        ),
    )

    id: Mapped[UUID] = mapped_column(UUID_COLUMN, primary_key=True, default=new_id)
    workspace_id: Mapped[UUID] = mapped_column(UUID_COLUMN, nullable=False)
    character_id: Mapped[UUID] = mapped_column(UUID_COLUMN, nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    bible_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="candidate", server_default="candidate"
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by_user_id: Mapped[UUID | None] = mapped_column(UUID_COLUMN, nullable=True)
    derived_from_version_id: Mapped[UUID | None] = mapped_column(UUID_COLUMN, nullable=True)


class Style(TimestampMixin, Base):
    __tablename__ = "styles"
    __table_args__ = (
        ForeignKeyConstraint(
            ["ip_id", "workspace_id"],
            ["ips.id", "ips.workspace_id"],
            name="fk_styles_ip_workspace",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "workspace_id", name="uq_styles_id_workspace"),
    )

    id: Mapped[UUID] = mapped_column(UUID_COLUMN, primary_key=True, default=new_id)
    workspace_id: Mapped[UUID] = mapped_column(UUID_COLUMN, nullable=False)
    ip_id: Mapped[UUID] = mapped_column(UUID_COLUMN, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)


class StyleVersion(TimestampMixin, Base):
    __tablename__ = "style_versions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["style_id", "workspace_id"],
            ["styles.id", "styles.workspace_id"],
            name="fk_style_versions_style_workspace",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["approved_by_user_id", "workspace_id"],
            ["users.id", "users.workspace_id"],
            name="fk_style_versions_approver_workspace",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["derived_from_version_id", "style_id"],
            ["style_versions.id", "style_versions.style_id"],
            name="fk_style_versions_parent_style",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("style_id", "version_no", name="uq_style_versions_style_version"),
        UniqueConstraint("id", "workspace_id", name="uq_style_versions_id_workspace"),
        UniqueConstraint("id", "style_id", name="uq_style_versions_id_style"),
        CheckConstraint("version_no > 0", name="ck_style_versions_version_positive"),
        CheckConstraint("status IN ('candidate', 'approved', 'archived')", name="ck_style_versions_status"),
    )

    id: Mapped[UUID] = mapped_column(UUID_COLUMN, primary_key=True, default=new_id)
    workspace_id: Mapped[UUID] = mapped_column(UUID_COLUMN, nullable=False)
    style_id: Mapped[UUID] = mapped_column(UUID_COLUMN, nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    bible_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="candidate", server_default="candidate"
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by_user_id: Mapped[UUID | None] = mapped_column(UUID_COLUMN, nullable=True)
    derived_from_version_id: Mapped[UUID | None] = mapped_column(UUID_COLUMN, nullable=True)
