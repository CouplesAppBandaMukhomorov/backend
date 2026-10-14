from typing import Annotated

from fastapi import APIRouter, Body, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_couple, get_current_user
from app.api.openapi import error_response
from app.db.session import get_db
from app.models.couple import Couple
from app.models.user import User
from app.schemas.couple import CoupleCreate, CoupleRead, CoupleUpdate
from app.services import couple_service

router = APIRouter(prefix="/couples", tags=["couples"])


@router.post(
    "",
    response_model=CoupleRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать пару",
    description=(
        "Создаёт пару и делает вызывающего её участником. Человек может состоять только "
        "в одной паре, поэтому повторный вызов вернёт `409`.\n\n"
        "Пара создаётся с одним участником — партнёр присоединяется позже через приглашение. "
        "Настройки можно передать сразу или потом через `PATCH /couples/me`."
    ),
    responses={
        409: error_response("Пользователь уже состоит в паре. Код: `already_in_couple`."),
    },
)
async def create_couple(
    payload: Annotated[
        CoupleCreate,
        Body(
            openapi_examples={
                "empty": {"summary": "Создать пустую пару", "value": {}},
                "with_settings": {
                    "summary": "Сразу указать дату и таймзону",
                    "value": {
                        "title": "Us",
                        "together_since": "2024-02-14",
                        "timezone": "Europe/Moscow",
                    },
                },
            }
        ),
    ],
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CoupleRead:
    return await couple_service.create_couple(db, user, payload)


@router.get(
    "/me",
    response_model=CoupleRead,
    summary="Получить состояние пары",
    description=(
        "Главный эндпоинт для экрана пары.\n\n"
        "- `members` — от одного до двух участников, отсортированы по времени вступления.\n"
        "- `days_together` — сколько дней пара вместе, считается по `together_since`. "
        "`null`, если дата не задана.\n"
        "- `calendar` — привязанный Google-календарь или `null`. Дублируется в `GET /couple/calendar`.\n\n"
        "Возвращает `404`, если пользователь ещё не состоит в паре."
    ),
    responses={
        404: error_response("Пользователь не состоит в паре. Код: `couple_not_found`."),
    },
)
async def read_couple(couple: Couple = Depends(get_current_couple)) -> CoupleRead:
    return couple_service.to_couple_read(couple)


@router.patch(
    "/me",
    response_model=CoupleRead,
    summary="Обновить настройки пары",
    description=(
        "Меняет только переданные поля.\n\n"
        "`timezone` используется как таймзона по умолчанию для новых событий, поэтому её стоит "
        "заполнить. `null` в `timezone` вернёт `422`. `title` можно очистить, передав `null`.\n\n"
        "Права у обоих партнёров одинаковые, кто именно вызывает — не важно."
    ),
    responses={
        404: error_response("Пользователь не состоит в паре. Код: `couple_not_found`."),
    },
)
async def update_couple(
    payload: Annotated[
        CoupleUpdate,
        Body(
            openapi_examples={
                "anniversary": {
                    "summary": "Указать, сколько уже вместе",
                    "value": {"together_since": "2024-02-14", "timezone": "Europe/Moscow"},
                },
                "rename": {"summary": "Переименовать пару", "value": {"title": "Our story"}},
            }
        ),
    ],
    couple: Couple = Depends(get_current_couple),
    db: AsyncSession = Depends(get_db),
) -> CoupleRead:
    return await couple_service.update_couple(db, couple, payload)


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Покинуть пару",
    description=(
        "Удаляет участника из пары. Побочные эффекты:\n\n"
        "- активные приглашения пары отменяются;\n"
        "- если вышел последний участник, пара удаляется целиком;\n"
        "- если вышел партнёр, чей Google-аккаунт владел календарём, привязка календаря "
        "снимается — оставшийся партнёр не продолжает работать через его токен.\n\n"
        "Тело ответа пустое."
    ),
    responses={
        404: error_response("Пользователь не состоит в паре. Код: `not_in_couple`."),
    },
)
async def leave_couple(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await couple_service.leave_couple(db, user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
