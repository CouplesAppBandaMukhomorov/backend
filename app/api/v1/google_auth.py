from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models.user import User
from app.schemas.google import GoogleAuthorizeUrl, GoogleCalendarRead, GoogleConnectionRead
from app.services import google_service

router = APIRouter(prefix="/google", tags=["google"])


@router.get("/connect", response_model=GoogleAuthorizeUrl)
async def connect(user: User = Depends(get_current_user)) -> GoogleAuthorizeUrl:
    return GoogleAuthorizeUrl(authorization_url=await google_service.build_connect_url(user))


@router.get("/callback", include_in_schema=False)
async def callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    settings = get_settings()
    target = settings.frontend_redirect_url
    separator = "&" if "?" in target else "?"
    if error is not None or code is None or state is None:
        return RedirectResponse(f"{target}{separator}google=error")
    try:
        await google_service.handle_callback(db, code, state)
    except Exception:
        return RedirectResponse(f"{target}{separator}google=error")
    return RedirectResponse(f"{target}{separator}google=connected")


@router.get("/connection", response_model=GoogleConnectionRead)
async def connection(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GoogleConnectionRead:
    return GoogleConnectionRead(**await google_service.connection_status(db, user))


@router.delete("/connection", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await google_service.disconnect(db, user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/calendars", response_model=list[GoogleCalendarRead])
async def calendars(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[GoogleCalendarRead]:
    items = await google_service.list_calendars(db, user)
    return [
        GoogleCalendarRead(
            id=item["id"],
            summary=item.get("summary") or item["id"],
            description=item.get("description"),
            timezone=item.get("timeZone"),
            access_role=item.get("accessRole"),
            primary=bool(item.get("primary", False)),
        )
        for item in items
    ]
