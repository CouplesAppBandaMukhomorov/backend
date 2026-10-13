import uuid
from datetime import date

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import Conflict, NotFound
from app.db.base import utcnow
from app.models.couple import Couple, CoupleMember
from app.models.invitation import Invitation, InvitationStatus
from app.models.user import User
from app.schemas.calendar import CalendarLink
from app.schemas.couple import CoupleCreate, CoupleRead, CoupleUpdate
from app.schemas.user import UserShort


def days_together(together_since: date | None) -> int | None:
    if together_since is None:
        return None
    return max((date.today() - together_since).days, 0)


def to_couple_read(couple: Couple) -> CoupleRead:
    calendar = None
    if couple.calendar_id and couple.calendar_owner_id:
        calendar = CalendarLink(
            calendar_id=couple.calendar_id,
            summary=couple.calendar_summary,
            owner_id=couple.calendar_owner_id,
        )
    members = [
        UserShort.model_validate(member.user)
        for member in sorted(couple.members, key=lambda item: item.joined_at)
    ]
    return CoupleRead(
        id=couple.id,
        title=couple.title,
        timezone=couple.timezone,
        together_since=couple.together_since,
        days_together=days_together(couple.together_since),
        created_at=couple.created_at,
        members=members,
        calendar=calendar,
    )


async def load_couple(db: AsyncSession, couple_id: uuid.UUID) -> Couple:
    stmt = (
        select(Couple)
        .where(Couple.id == couple_id)
        .options(selectinload(Couple.members).selectinload(CoupleMember.user))
    )
    couple = (await db.execute(stmt)).scalar_one_or_none()
    if couple is None:
        raise NotFound("Couple not found", code="couple_not_found")
    return couple


async def get_membership(db: AsyncSession, user_id: uuid.UUID) -> CoupleMember | None:
    result = await db.execute(select(CoupleMember).where(CoupleMember.user_id == user_id))
    return result.scalar_one_or_none()


async def count_members(db: AsyncSession, couple_id: uuid.UUID) -> int:
    result = await db.execute(select(CoupleMember.user_id).where(CoupleMember.couple_id == couple_id))
    return len(result.scalars().all())


async def create_couple(db: AsyncSession, user: User, payload: CoupleCreate) -> CoupleRead:
    if await get_membership(db, user.id) is not None:
        raise Conflict("You are already in a couple", code="already_in_couple")
    couple = Couple(
        title=payload.title,
        timezone=payload.timezone,
        together_since=payload.together_since,
    )
    db.add(couple)
    await db.flush()
    db.add(CoupleMember(couple_id=couple.id, user_id=user.id))
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise Conflict("You are already in a couple", code="already_in_couple") from exc
    return to_couple_read(await load_couple(db, couple.id))


async def update_couple(db: AsyncSession, couple: Couple, payload: CoupleUpdate) -> CoupleRead:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(couple, field, value)
    await db.commit()
    return to_couple_read(await load_couple(db, couple.id))


async def leave_couple(db: AsyncSession, user: User) -> None:
    membership = await get_membership(db, user.id)
    if membership is None:
        raise NotFound("You are not in a couple", code="not_in_couple")

    couple_id = membership.couple_id
    await db.delete(membership)
    await db.flush()

    couple = await db.get(Couple, couple_id)
    if couple is not None and couple.calendar_owner_id == user.id:
        couple.calendar_id = None
        couple.calendar_summary = None
        couple.calendar_owner_id = None

    reminders = (
        await db.execute(
            select(Invitation).where(
                Invitation.couple_id == couple_id,
                Invitation.status == InvitationStatus.PENDING.value,
            )
        )
    ).scalars().all()
    for invitation in reminders:
        invitation.status = InvitationStatus.CANCELLED.value
        invitation.responded_at = utcnow()

    if await count_members(db, couple_id) == 0:
        await db.execute(delete(Invitation).where(Invitation.couple_id == couple_id))
        await db.execute(delete(Couple).where(Couple.id == couple_id))

    await db.commit()
