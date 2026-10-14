from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.openapi import error_response
from app.core.config import get_settings
from app.db.session import get_db
from app.models.user import User
from app.schemas.google import GoogleAuthorizeUrl, GoogleCalendarRead, GoogleConnectionRead
from app.services import google_service

router = APIRouter(prefix="/google", tags=["google"])


@router.get(
    "/connect",
    response_model=GoogleAuthorizeUrl,
    summary="Начать подключение Google-аккаунта",
    description=(
        "Возвращает `authorization_url`, по которой фронт открывает согласие Google.\n\n"
        "Порядок действий:\n"
        "1. Открыть полученную ссылку в системном браузере (в iframe Google согласие не проведёт).\n"
        "2. Пользователь даёт согласие на доступ к календарю.\n"
        "3. Google возвращает его на бэкенд, а бэкенд редиректит на `FRONTEND_REDIRECT_URL` "
        "с параметром `google=connected` или `google=error`.\n"
        "4. Проверить результат через `GET /google/connection`.\n\n"
        "Ссылка подписана под конкретного пользователя и живёт 10 минут, повторный вызов создаёт новую."
    ),
)
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


@router.get(
    "/connection",
    response_model=GoogleConnectionRead,
    summary="Статус подключения Google",
    description=(
        "Показывает, подключён ли Google-аккаунт у текущего пользователя, какие права выданы "
        "и до какого момента действует access-токен.\n\n"
        "Смысл для фронта: после возврата из Google-согласия проверить `connected` и отрисовать "
        "следующий шаг — выбор календаря.\n\n"
        "`connected: false` — это не ошибка, а обычное состояние."
    ),
)
async def connection(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GoogleConnectionRead:
    return GoogleConnectionRead(**await google_service.connection_status(db, user))


@router.delete(
    "/connection",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Отключить Google-аккаунт",
    description=(
        "Отзывает токены в Google, удаляет сохранённые креды и **снимает привязку календаря** "
        "с тех пар, где владельцем календаря был этот пользователь. После этого события пары "
        "недоступны, пока календарь не привяжут заново.\n\n"
        "Тело ответа пустое."
    ),
)
async def disconnect(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await google_service.disconnect(db, user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/calendars",
    response_model=list[GoogleCalendarRead],
    summary="Список календарей для привязки",
    description=(
        "Отдаёт календари подключённого Google-аккаунта, доступные **на запись** "
        "(`minAccessRole=writer`). Read-only календари сюда не попадают.\n\n"
        "Что делать дальше: показать список пользователю и отправить выбранный `id` "
        "в `PUT /couple/calendar`.\n\n"
        "Список читается напрямую из Google в момент запроса, кэша нет."
    ),
    responses={
        403: error_response(
            "Google отказал в доступе: права отозваны или недостаточны. Код: `google_access_denied`."
        ),
        409: error_response(
            "Google-аккаунт не подключён или требует повторного подключения. "
            "Коды: `google_not_connected`, `google_reconnect_required`."
        ),
        502: error_response("Google Calendar API вернул ошибку. Код: `google_api_error`."),
    },
)
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
