import secrets
import string
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.config import get_settings
from app.core.errors import BadRequest, Conflict, Forbidden, NotFound
from app.db.base import utcnow
from app.models.couple import Couple, CoupleMember
from app.models.invitation import Invitation, InvitationStatus
from app.models.user import User
from app.schemas.invitation import InvitationAcceptResponse, InvitationPreview, InvitationRead
from app.schemas.user import UserShort
from app.services import couple_service

CODE_ALPHABET = string.ascii_uppercase + string.digits
CODE_LENGTH = 8


def _generate_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def to_invitation_read(invitation: Invitation) -> InvitationRead:
    return InvitationRead(
        id=invitation.id,
        couple_id=invitation.couple_id,
        code=invitation.code,
        status=invitation.status,
        expires_at=invitation.expires_at,
        created_at=invitation.created_at,
        inviter=UserShort.model_validate(invitation.inviter),
        invited_user=(
            UserShort.model_validate(invitation.invited_user) if invitation.invited_user else None
        ),
    )


async def load_by_id(db: AsyncSession, invitation_id: uuid.UUID) -> Invitation:
    stmt = (
        select(Invitation)
        .where(Invitation.id == invitation_id)
        .options(joinedload(Invitation.inviter), joinedload(Invitation.invited_user))
    )
    invitation = (await db.execute(stmt)).scalar_one_or_none()
    if invitation is None:
        raise NotFound("Invitation not found", code="invitation_not_found")
    return invitation


async def load_by_code(db: AsyncSession, code: str) -> Invitation:
    stmt = (
        select(Invitation)
        .where(Invitation.code == code.strip().upper())
        .options(joinedload(Invitation.inviter), joinedload(Invitation.invited_user))
    )
    invitation = (await db.execute(stmt)).scalar_one_or_none()
    if invitation is None:
        raise NotFound("Invitation not found", code="invitation_not_found")
    return invitation


async def create_invitation(db: AsyncSession, user: User) -> InvitationRead:
    settings = get_settings()
    membership = await couple_service.get_membership(db, user.id)
    if membership is None:
        raise Conflict("Create a couple before inviting a partner", code="couple_required")
    if await couple_service.count_members(db, membership.couple_id) >= 2:
        raise Conflict("Your couple already has two members", code="couple_is_full")

    pending = (
        await db.execute(
            select(Invitation).where(
                Invitation.couple_id == membership.couple_id,
                Invitation.status == InvitationStatus.PENDING.value,
            )
        )
    ).scalars().all()
    for invitation in pending:
        invitation.status = InvitationStatus.CANCELLED.value
        invitation.responded_at = utcnow()

    invitation = Invitation(
        couple_id=membership.couple_id,
        inviter_id=user.id,
        code=_generate_code(),
        status=InvitationStatus.PENDING.value,
        expires_at=utcnow() + timedelta(days=settings.invitation_ttl_days),
    )
    db.add(invitation)
    await db.commit()
    return to_invitation_read(await load_by_id(db, invitation.id))


async def get_active_invitation(db: AsyncSession, user: User) -> InvitationRead | None:
    membership = await couple_service.get_membership(db, user.id)
    if membership is None:
        return None
    invitation = (
        await db.execute(
            select(Invitation)
            .where(
                Invitation.couple_id == membership.couple_id,
                Invitation.status == InvitationStatus.PENDING.value,
            )
            .options(joinedload(Invitation.inviter), joinedload(Invitation.invited_user))
            .order_by(Invitation.created_at.desc())
        )
    ).scalars().first()
    if invitation is None:
        return None
    if _ensure_aware(invitation.expires_at) <= utcnow():
        invitation.status = InvitationStatus.EXPIRED.value
        await db.commit()
        return None
    return to_invitation_read(invitation)


async def get_preview(db: AsyncSession, code: str) -> InvitationPreview:
    invitation = await load_by_code(db, code)
    if invitation.status == InvitationStatus.PENDING.value and _ensure_aware(invitation.expires_at) <= utcnow():
        invitation.status = InvitationStatus.EXPIRED.value
        await db.commit()
    couple = await db.get(Couple, invitation.couple_id)
    return InvitationPreview(
        code=invitation.code,
        status=invitation.status,
        couple_id=invitation.couple_id,
        couple_title=couple.title if couple else None,
        expires_at=invitation.expires_at,
        inviter=UserShort.model_validate(invitation.inviter),
    )


async def accept_invitation(db: AsyncSession, user: User, code: str) -> InvitationAcceptResponse:
    invitation = await load_by_code(db, code)
    if invitation.status != InvitationStatus.PENDING.value:
        raise Conflict("Invitation is no longer active", code="invitation_not_active")
    if _ensure_aware(invitation.expires_at) <= utcnow():
        invitation.status = InvitationStatus.EXPIRED.value
        await db.commit()
        raise Conflict("Invitation has expired", code="invitation_expired")
    if invitation.inviter_id == user.id:
        raise BadRequest("You cannot accept your own invitation", code="cannot_accept_own_invitation")
    if await couple_service.get_membership(db, user.id) is not None:
        raise Conflict("You are already in a couple", code="already_in_couple")

    await db.execute(select(Couple).where(Couple.id == invitation.couple_id).with_for_update())
    if await couple_service.count_members(db, invitation.couple_id) >= 2:
        raise Conflict("This couple already has two members", code="couple_is_full")

    db.add(CoupleMember(couple_id=invitation.couple_id, user_id=user.id))
    invitation.invited_user_id = user.id
    invitation.status = InvitationStatus.ACCEPTED.value
    invitation.responded_at = utcnow()
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise Conflict("You are already in a couple", code="already_in_couple") from exc

    couple = await couple_service.load_couple(db, invitation.couple_id)
    return InvitationAcceptResponse(couple=couple_service.to_couple_read(couple))


async def cancel_invitation(db: AsyncSession, user: User, code: str) -> None:
    invitation = await load_by_code(db, code)
    if invitation.inviter_id != user.id:
        raise Forbidden("Only the inviter can cancel this invitation", code="not_inviter")
    if invitation.status == InvitationStatus.PENDING.value:
        invitation.status = InvitationStatus.CANCELLED.value
        invitation.responded_at = utcnow()
        await db.commit()
