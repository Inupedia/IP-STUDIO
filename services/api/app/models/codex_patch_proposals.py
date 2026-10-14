from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUID_COLUMN, new_id


class CodexPatchProposal(TimestampMixin, Base):
    __tablename__ = "codex_patch_proposals"
    __table_args__ = (
        ForeignKeyConstraint(
            ["ip_id", "workspace_id"],
            ["ips.id", "ips.workspace_id"],
            name="fk_codex_patch_proposals_ip_workspace",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["episode_id", "workspace_id"],
            ["episodes.id", "episodes.workspace_id"],
            name="fk_codex_patch_proposals_episode_workspace",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["document_id", "workspace_id", "episode_id"],
            ["episode_documents.id", "episode_documents.workspace_id", "episode_documents.episode_id"],
            name="fk_codex_patch_proposals_document_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["created_by_user_id", "workspace_id"],
            ["users.id", "users.workspace_id"],
            name="fk_codex_patch_proposals_creator_workspace",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["reviewed_by_user_id", "workspace_id"],
            ["users.id", "users.workspace_id"],
            name="fk_codex_patch_proposals_reviewer_workspace",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("approval_id", name="uq_codex_patch_proposals_approval_id"),
        UniqueConstraint("id", "workspace_id", name="uq_codex_patch_proposals_id_workspace"),
        CheckConstraint(
            "status IN ('pending_approval', 'approved', 'rejected')",
            name="ck_codex_patch_proposals_status",
        ),
        CheckConstraint("base_revision >= 0", name="ck_codex_patch_proposals_base_revision"),
        CheckConstraint(
            "(status = 'pending_approval' AND reviewed_at IS NULL AND reviewed_by_user_id IS NULL AND applied_revision IS NULL) "
            "OR (status = 'approved' AND reviewed_at IS NOT NULL AND reviewed_by_user_id IS NOT NULL AND applied_revision = base_revision + 1) "
            "OR (status = 'rejected' AND reviewed_at IS NOT NULL AND reviewed_by_user_id IS NOT NULL AND applied_revision IS NULL)",
            name="ck_codex_patch_proposals_review_state",
        ),
    )

    id: Mapped[UUID] = mapped_column(UUID_COLUMN, primary_key=True, default=new_id)
    approval_id: Mapped[UUID] = mapped_column(UUID_COLUMN, nullable=False, default=new_id)
    workspace_id: Mapped[UUID] = mapped_column(UUID_COLUMN, nullable=False)
    ip_id: Mapped[UUID] = mapped_column(UUID_COLUMN, nullable=False)
    episode_id: Mapped[UUID] = mapped_column(UUID_COLUMN, nullable=False)
    document_id: Mapped[UUID] = mapped_column(UUID_COLUMN, nullable=False)
    base_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    patch_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    preview_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending_approval")
    created_by_user_id: Mapped[UUID] = mapped_column(UUID_COLUMN, nullable=False)
    reviewed_by_user_id: Mapped[UUID | None] = mapped_column(UUID_COLUMN, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    applied_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
