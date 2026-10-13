import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User


class InvitationStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class Invitation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "invitations"

    couple_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("couples.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    inviter_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    invited_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=InvitationStatus.PENDING.value,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    inviter: Mapped["User"] = relationship(foreign_keys=[inviter_id])
    invited_user: Mapped["User | None"] = relationship(foreign_keys=[invited_user_id])
