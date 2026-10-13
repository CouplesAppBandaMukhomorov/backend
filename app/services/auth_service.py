import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import Conflict, Unauthorized
from app.core.security import (
    REFRESH_TOKEN_TYPE,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.integrations.google.oauth import verify_id_token
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenPair


def issue_tokens(user: User) -> TokenPair:
    settings = get_settings()
    return TokenPair(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
        expires_in=settings.access_token_ttl_minutes * 60,
    )


async def get_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email.lower()))
    return result.scalar_one_or_none()


async def register(db: AsyncSession, payload: RegisterRequest) -> TokenPair:
    if await get_by_email(db, payload.email) is not None:
        raise Conflict("This email is already registered", code="email_already_registered")
    user = User(
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        display_name=payload.display_name.strip(),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return issue_tokens(user)


async def login(db: AsyncSession, payload: LoginRequest) -> TokenPair:
    user = await get_by_email(db, payload.email)
    if user is None or user.password_hash is None:
        raise Unauthorized("Invalid email or password", code="invalid_credentials")
    if not verify_password(payload.password, user.password_hash):
        raise Unauthorized("Invalid email or password", code="invalid_credentials")
    return issue_tokens(user)


async def login_with_google(db: AsyncSession, id_token: str) -> TokenPair:
    claims = await verify_id_token(id_token)
    google_sub = claims["sub"]
    email = claims["email"].lower()

    result = await db.execute(select(User).where(User.google_sub == google_sub))
    user = result.scalar_one_or_none()
    if user is not None:
        return issue_tokens(user)

    user = await get_by_email(db, email)
    if user is None:
        user = User(
            email=email,
            password_hash=None,
            google_sub=google_sub,
            display_name=claims.get("name") or email.split("@")[0],
            avatar_url=claims.get("picture"),
        )
        db.add(user)
    else:
        user.google_sub = google_sub
        if user.avatar_url is None:
            user.avatar_url = claims.get("picture")
    await db.commit()
    await db.refresh(user)
    return issue_tokens(user)


async def refresh(db: AsyncSession, refresh_token: str) -> TokenPair:
    payload = decode_token(refresh_token, REFRESH_TOKEN_TYPE)
    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise Unauthorized("Invalid refresh token", code="invalid_token") from exc
    user = await db.get(User, user_id)
    if user is None:
        raise Unauthorized("User no longer exists", code="invalid_token")
    return issue_tokens(user)
