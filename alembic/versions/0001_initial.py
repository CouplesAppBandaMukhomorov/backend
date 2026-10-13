from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("google_sub", sa.String(length=255), nullable=True),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("avatar_url", sa.String(length=1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_google_sub", "users", ["google_sub"], unique=True)

    op.create_table(
        "couples",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=True),
        sa.Column("together_since", sa.Date(), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("calendar_id", sa.String(length=255), nullable=True),
        sa.Column("calendar_summary", sa.String(length=255), nullable=True),
        sa.Column("calendar_owner_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["calendar_owner_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "couple_members",
        sa.Column("couple_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["couple_id"], ["couples.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("couple_id", "user_id"),
    )
    op.create_index("ix_couple_members_user_id", "couple_members", ["user_id"], unique=True)

    op.create_table(
        "invitations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("couple_id", sa.Uuid(), nullable=False),
        sa.Column("inviter_id", sa.Uuid(), nullable=False),
        sa.Column("invited_user_id", sa.Uuid(), nullable=True),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["couple_id"], ["couples.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["inviter_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invited_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_invitations_code", "invitations", ["code"], unique=True)
    op.create_index("ix_invitations_couple_id", "invitations", ["couple_id"], unique=False)
    op.create_index("ix_invitations_inviter_id", "invitations", ["inviter_id"], unique=False)

    op.create_table(
        "google_credentials",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("access_token", sa.Text(), nullable=False),
        sa.Column("refresh_token", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scope", sa.String(length=1024), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_google_credentials_user_id", "google_credentials", ["user_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_google_credentials_user_id", table_name="google_credentials")
    op.drop_table("google_credentials")
    op.drop_index("ix_invitations_inviter_id", table_name="invitations")
    op.drop_index("ix_invitations_couple_id", table_name="invitations")
    op.drop_index("ix_invitations_code", table_name="invitations")
    op.drop_table("invitations")
    op.drop_index("ix_couple_members_user_id", table_name="couple_members")
    op.drop_table("couple_members")
    op.drop_table("couples")
    op.drop_index("ix_users_google_sub", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
