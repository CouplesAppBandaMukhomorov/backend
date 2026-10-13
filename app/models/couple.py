import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utcnow

if TYPE_CHECKING:
    from app.models.user import User


class Couple(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "couples"

    title: Mapped[str | None] = mapped_column(String(120), nullable=True)
    together_since: Mapped[date | None] = mapped_column(Date, nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    calendar_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    calendar_summary: Mapped[str | None] = mapped_column(String(255), nullable=True)
    calendar_owner_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    members: Mapped[list["CoupleMember"]] = relationship(back_populates="couple")


class CoupleMember(Base):
    __tablename__ = "couple_members"

    couple_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("couples.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        unique=True,
        index=True,
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
    )

    couple: Mapped[Couple] = relationship(back_populates="members")
    user: Mapped["User"] = relationship(back_populates="membership")
