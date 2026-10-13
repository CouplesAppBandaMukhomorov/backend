import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import crypto
from app.core.errors import GoogleNotConnected, Unauthorized
from app.core.security import OAUTH_STATE_TYPE, create_oauth_state, decode_token
from app.integrations.google import oauth as google_oauth
from app.integrations.google.calendar import GoogleCalendarClient
from app.models.couple import Couple
from app.models.google_credential import GoogleCredential
from app.models.user import User

TOKEN_REFRESH_SKEW = timedelta(minutes=5)


async def build_connect_url(user: User) -> str:
    return google_oauth.build_authorization_url(create_oauth_state(user.id))


def parse_state(state: str) -> uuid.UUID:
    payload = decode_token(state, OAUTH_STATE_TYPE)
    try:
        return uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise Unauthorized("Invalid OAuth state", code="invalid_oauth_state") from exc


async def get_credential(db: AsyncSession, user_id: uuid.UUID) -> GoogleCredential | None:
    result = await db.execute(select(GoogleCredential).where(GoogleCredential.user_id == user_id))
    return result.scalar_one_or_none()


async def save_credentials(db: AsyncSession, user_id: uuid.UUID, token_data: dict) -> GoogleCredential:
    expires_in = int(token_data.get("expires_in", 3600))
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    encrypted_access = crypto.encrypt(token_data["access_token"])
    encrypted_refresh = (
        crypto.encrypt(token_data["refresh_token"]) if token_data.get("refresh_token") else None
    )

    credential = await get_credential(db, user_id)
    if credential is None:
        credential = GoogleCredential(
            user_id=user_id,
            access_token=encrypted_access,
            refresh_token=encrypted_refresh,
            expires_at=expires_at,
            scope=token_data.get("scope", ""),
        )
        db.add(credential)
    else:
        credential.access_token = encrypted_access
        if encrypted_refresh is not None:
            credential.refresh_token = encrypted_refresh
        credential.expires_at = expires_at
        credential.scope = token_data.get("scope", credential.scope)
    await db.commit()
    await db.refresh(credential)
    return credential


async def handle_callback(db: AsyncSession, code: str, state: str) -> uuid.UUID:
    user_id = parse_state(state)
    token_data = await google_oauth.exchange_code(code)
    await save_credentials(db, user_id, token_data)
    return user_id


async def get_access_token(db: AsyncSession, user_id: uuid.UUID) -> str:
    credential = await get_credential(db, user_id)
    if credential is None:
        raise GoogleNotConnected("Google account is not connected", code="google_not_connected")

    expires_at = credential.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    if expires_at - TOKEN_REFRESH_SKEW > now:
        return crypto.decrypt(credential.access_token)

    if credential.refresh_token is None:
        raise GoogleNotConnected(
            "Google refresh token is missing, reconnect the account",
            code="google_reconnect_required",
        )

    token_data = await google_oauth.refresh_access_token(crypto.decrypt(credential.refresh_token))
    await save_credentials(db, user_id, token_data)
    return token_data["access_token"]


async def connection_status(db: AsyncSession, user: User) -> dict:
    credential = await get_credential(db, user.id)
    if credential is None:
        return {"connected": False, "scope": None, "expires_at": None}
    return {"connected": True, "scope": credential.scope, "expires_at": credential.expires_at}


async def list_calendars(db: AsyncSession, user: User) -> list[dict]:
    access_token = await get_access_token(db, user.id)
    async with GoogleCalendarClient(access_token) as client:
        return await client.list_calendars()


async def disconnect(db: AsyncSession, user: User) -> None:
    credential = await get_credential(db, user.id)

    couples = (
        await db.execute(select(Couple).where(Couple.calendar_owner_id == user.id))
    ).scalars().all()
    for couple in couples:
        couple.calendar_id = None
        couple.calendar_summary = None
        couple.calendar_owner_id = None

    if credential is not None:
        for token in (credential.refresh_token, credential.access_token):
            if token is None:
                continue
            try:
                await google_oauth.revoke_token(crypto.decrypt(token))
            except Exception:
                continue
        await db.delete(credential)

    await db.commit()
