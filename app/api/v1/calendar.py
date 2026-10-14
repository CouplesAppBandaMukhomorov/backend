from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_couple, get_current_user
from app.api.openapi import error_response
from app.db.session import get_db
from app.models.couple import Couple
from app.models.user import User
from app.schemas.calendar import (
    CalendarLink,
    CalendarLinkRequest,
    EventCreate,
    EventRead,
    EventUpdate,
)
from app.services import calendar_service

router = APIRouter(prefix="/couple/calendar", tags=["calendar"])

COUPLE_NOT_FOUND = error_response(
    "Пользователь не состоит в паре, поэтому календаря у него нет. Код: `couple_not_found`."
)
CALENDAR_NOT_LINKED = error_response(
    "К паре не привязан Google-календарь. Сначала `PUT /couple/calendar`. Код: `calendar_not_linked`."
)
GOOGLE_UNAVAILABLE = error_response(
    "Проблема с Google-аккаунтом или самим Google. Коды: `google_not_connected`, "
    "`google_reconnect_required`, `google_access_denied`, `google_api_error`."
)
EVENT_ID_PATH = Path(
    description=(
        "Идентификатор события в Google из ответов `GET /couple/calendar/events` или "
        "`POST /couple/calendar/events`. Для события из серии это идентификатор конкретного "
        "вхождения вида `abc123_20261013T160000Z`."
    ),
    examples=["6k3vk8bq1abc"],
)
TIME_MIN_QUERY = Query(
    description=(
        "Начало окна выборки, ISO 8601. Если не передано — текущий момент. "
        "Смещение передавайте через `Z` либо кодируйте `+` как `%2B`."
    ),
    examples=["2026-10-01T00:00:00Z"],
)
TIME_MAX_QUERY = Query(
    description=(
        "Конец окна выборки, ISO 8601, должен быть больше `time_min`. "
        "Если не передано — `time_min` плюс 30 дней."
    ),
    examples=["2026-11-01T00:00:00Z"],
)


@router.get(
    "",
    response_model=CalendarLink | None,
    summary="Получить привязанный календарь",
    description=(
        "Возвращает привязанный Google-календарь пары или `null`, если он ещё не привязан. "
        "`null` — это не ошибка.\n\n"
        "То же значение лежит в поле `calendar` ответа `GET /couples/me`."
    ),
    responses={404: COUPLE_NOT_FOUND},
)
async def read_link(couple: Couple = Depends(get_current_couple)) -> CalendarLink | None:
    return calendar_service.get_link(couple)


@router.put(
    "",
    response_model=CalendarLink,
    summary="Привязать Google-календарь к паре",
    description=(
        "Привязывает календарь из списка `GET /google/calendars`. Привязать может любой из "
        "партнёров, но календарь должен быть доступен **на запись его** Google-аккаунту: "
        "это важно, потому что дальше бэкенд работает токеном владельца календаря, "
        "а не того, кто нажимает кнопку в интерфейсе.\n\n"
        "После привязки события читаются и пишутся сразу в этот календарь, копирования нет. "
        "Повторный вызов просто заменяет привязку."
    ),
    responses={
        400: error_response(
            "Календарь недоступен аккаунту или доступен только для чтения. "
            "Коды: `calendar_not_available`, `calendar_not_writable`."
        ),
        404: COUPLE_NOT_FOUND,
        409: error_response(
            "Google-аккаунт не подключён или требует повторного подключения. "
            "Коды: `google_not_connected`, `google_reconnect_required`."
        ),
        502: error_response("Google Calendar API вернул ошибку. Код: `google_api_error`."),
    },
)
async def link_calendar(
    payload: Annotated[
        CalendarLinkRequest,
        Body(
            openapi_examples={
                "basic": {
                    "summary": "Привязать календарь по id из GET /google/calendars",
                    "value": {"calendar_id": "abc123@group.calendar.google.com"},
                }
            }
        ),
    ],
    couple: Couple = Depends(get_current_couple),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CalendarLink:
    return await calendar_service.link_calendar(db, couple, user, payload.calendar_id)


@router.delete(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Отвязать календарь",
    description=(
        "Снимает привязку календаря с пары. Сам календарь и события в нём не трогает, "
        "Google-аккаунт остаётся подключённым: можно привязать другой календарь.\n\n"
        "Пока календарь не привязан заново, события недоступны и вернут `calendar_not_linked`."
    ),
    responses={404: COUPLE_NOT_FOUND},
)
async def unlink_calendar(
    couple: Couple = Depends(get_current_couple),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await calendar_service.unlink_calendar(db, couple)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/events",
    response_model=list[EventRead],
    summary="Список событий пары",
    description=(
        "Читает события прямо из Google Calendar в момент запроса, у нас они не хранятся.\n\n"
        "- Без параметров: от текущего момента на 30 дней вперёд.\n"
        "- Повторяющиеся события возвращаются развёрнутыми, по объекту на вхождение, "
        "отсортированными по началу.\n"
        "- Отменённые события в ответ не попадают.\n"
        "- Максимум 5000 событий за запрос, пагинации нет — сужайте окно.\n\n"
        "Изменения, сделанные партнёром прямо в Google Calendar, будут видны здесь при "
        "следующем запросе: фоновой синхронизации и вебхуков нет."
    ),
    responses={
        400: error_response("`time_max` не больше `time_min`. Код: `invalid_time_range`."),
        404: COUPLE_NOT_FOUND,
        409: CALENDAR_NOT_LINKED,
        502: GOOGLE_UNAVAILABLE,
    },
)
async def list_events(
    time_min: Annotated[datetime | None, TIME_MIN_QUERY] = None,
    time_max: Annotated[datetime | None, TIME_MAX_QUERY] = None,
    couple: Couple = Depends(get_current_couple),
    db: AsyncSession = Depends(get_db),
) -> list[EventRead]:
    return await calendar_service.list_events(db, couple, time_min, time_max)


@router.post(
    "/events",
    response_model=EventRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать событие",
    description=(
        "Создаёт событие в привязанном Google-календаре. Оно сразу появится в приложении "
        "Google Calendar: это тот же самый календарь, отдельной синхронизации нет.\n\n"
        "Правила времени:\n"
        "- в `start` и `end` нужно ровно одно из `date` или `date_time`;\n"
        "- `date` создаёт событие на весь день, при этом `end` в Google исключающий: "
        "на один день передавайте `start.date = 2026-06-01`, `end.date = 2026-06-02`;\n"
        "- наивный `date_time` трактуется в таймзоне из `time_zone`, а если её нет — "
        "в таймзоне пары."
    ),
    responses={
        404: COUPLE_NOT_FOUND,
        409: CALENDAR_NOT_LINKED,
        502: GOOGLE_UNAVAILABLE,
    },
)
async def create_event(
    payload: Annotated[
        EventCreate,
        Body(
            openapi_examples={
                "timed": {
                    "summary": "Встреча с конкретным временем",
                    "value": {
                        "summary": "Ужин",
                        "description": "Итальянский ресторан",
                        "location": "ул. Пушкина, 1",
                        "start": {
                            "date_time": "2026-10-14T19:00:00+03:00",
                            "time_zone": "Europe/Moscow",
                        },
                        "end": {
                            "date_time": "2026-10-14T21:00:00+03:00",
                            "time_zone": "Europe/Moscow",
                        },
                        "attendees": ["partner@example.com"],
                        "reminders": {"use_default": True},
                    },
                },
                "all_day": {
                    "summary": "Событие на весь день",
                    "value": {
                        "summary": "Годовщина",
                        "start": {"date": "2026-06-01"},
                        "end": {"date": "2026-06-02"},
                    },
                },
            }
        ),
    ],
    couple: Couple = Depends(get_current_couple),
    db: AsyncSession = Depends(get_db),
) -> EventRead:
    return await calendar_service.create_event(db, couple, payload)


@router.get(
    "/events/{event_id}",
    response_model=EventRead,
    summary="Получить одно событие",
    description=(
        "Отдаёт событие по идентификатору Google. Пригодится, чтобы обновить карточку после "
        "правки или проверить, что событие ещё существует."
    ),
    responses={
        404: error_response("Событие не найдено в Google: удалено или недоступно. Код: `calendar_not_found`."),
        409: CALENDAR_NOT_LINKED,
        502: GOOGLE_UNAVAILABLE,
    },
)
async def read_event(
    event_id: Annotated[str, EVENT_ID_PATH],
    couple: Couple = Depends(get_current_couple),
    db: AsyncSession = Depends(get_db),
) -> EventRead:
    return await calendar_service.get_event(db, couple, event_id)


@router.patch(
    "/events/{event_id}",
    response_model=EventRead,
    summary="Изменить событие",
    description=(
        "Частичное обновление: меняются только переданные поля.\n\n"
        "Очистить `description` или `location` нельзя, их можно только заменить. "
        "Пустое тело вернёт `400` с кодом `empty_update`.\n\n"
        "Для события из серии меняется только это вхождение, вся серия целиком — нет."
    ),
    responses={
        400: error_response(
            "В теле не передано ни одного поля для изменения. Код: `empty_update`."
        ),
        404: error_response("Событие не найдено в Google. Код: `calendar_not_found`."),
        409: CALENDAR_NOT_LINKED,
        502: GOOGLE_UNAVAILABLE,
    },
)
async def update_event(
    event_id: Annotated[str, EVENT_ID_PATH],
    payload: Annotated[
        EventUpdate,
        Body(
            openapi_examples={
                "rename": {"summary": "Перенести время и переименовать", "value": {
                    "summary": "Ужин перенесён",
                    "start": {"date_time": "2026-10-15T20:00:00+03:00", "time_zone": "Europe/Moscow"},
                    "end": {"date_time": "2026-10-15T22:00:00+03:00", "time_zone": "Europe/Moscow"},
                }},
                "location": {"summary": "Сменить место", "value": {"location": "ул. Ленина, 5"}},
            }
        ),
    ],
    couple: Couple = Depends(get_current_couple),
    db: AsyncSession = Depends(get_db),
) -> EventRead:
    return await calendar_service.update_event(db, couple, event_id, payload)


@router.delete(
    "/events/{event_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить событие",
    description=(
        "Удаляет событие из Google-календаря пары. Тело ответа пустое.\n\n"
        "Для события из серии удаляется только это вхождение."
    ),
    responses={
        404: error_response("Событие не найдено в Google. Код: `calendar_not_found`."),
        409: CALENDAR_NOT_LINKED,
        502: GOOGLE_UNAVAILABLE,
    },
)
async def delete_event(
    event_id: Annotated[str, EVENT_ID_PATH],
    couple: Couple = Depends(get_current_couple),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await calendar_service.delete_event(db, couple, event_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
