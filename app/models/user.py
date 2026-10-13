from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.couple import CoupleMember
    from app.models.google_credential import GoogleCredential


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    google_sub: Mapped[str | None] = mapped_column(String(255), unique=True, index=True, nullable=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    membership: Mapped["CoupleMember | None"] = relationship(back_populates="user", uselist=False)
    credential: Mapped["GoogleCredential | None"] = relationship(back_populates="user", uselist=False)
