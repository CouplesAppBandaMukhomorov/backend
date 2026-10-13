import uuid

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import NotFound, Unauthorized
from app.core.security import ACCESS_TOKEN_TYPE, decode_token
from app.db.session import get_db
from app.models.couple import Couple, CoupleMember
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise Unauthorized("Authorization header is missing", code="missing_token")
    payload = decode_token(credentials.credentials, ACCESS_TOKEN_TYPE)
    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise Unauthorized("Token subject is invalid", code="invalid_token") from exc
    user = await db.get(User, user_id)
    if user is None:
        raise Unauthorized("User no longer exists", code="invalid_token")
    return user


async def get_current_membership(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CoupleMember:
    result = await db.execute(select(CoupleMember).where(CoupleMember.user_id == user.id))
    membership = result.scalar_one_or_none()
    if membership is None:
        raise NotFound("You are not in a couple yet", code="couple_not_found")
    return membership


async def get_current_couple(
    membership: CoupleMember = Depends(get_current_membership),
    db: AsyncSession = Depends(get_db),
) -> Couple:
    stmt = (
        select(Couple)
        .where(Couple.id == membership.couple_id)
        .options(selectinload(Couple.members).selectinload(CoupleMember.user))
    )
    couple = (await db.execute(stmt)).scalar_one_or_none()
    if couple is None:
        raise NotFound("Couple not found", code="couple_not_found")
    return couple
