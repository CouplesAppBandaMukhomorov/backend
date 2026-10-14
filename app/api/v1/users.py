from typing import Annotated

from fastapi import APIRouter, Body, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserRead, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/me",
    response_model=UserRead,
    summary="Получить свой профиль",
    description=(
        "Данные аккаунта: email, имя, аватар. Пары и календаря здесь нет — для этого "
        "используйте `GET /couples/me`."
    ),
)
async def read_me(user: User = Depends(get_current_user)) -> UserRead:
    return UserRead.model_validate(user)


@router.patch(
    "/me",
    response_model=UserRead,
    summary="Обновить свой профиль",
    description=(
        "Меняет только переданные поля: чего нет в теле, то не изменится.\n\n"
        "`display_name` — обязательное поле, `null` в нём вернёт `422`. "
        "`avatar_url` можно очистить, передав `null`."
    ),
)
async def update_me(
    payload: Annotated[
        UserUpdate,
        Body(
            openapi_examples={
                "rename": {"summary": "Сменить имя", "value": {"display_name": "Ann Cooper"}},
                "clear_avatar": {"summary": "Убрать аватар", "value": {"avatar_url": None}},
            }
        ),
    ],
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserRead:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    await db.commit()
    await db.refresh(user)
    return UserRead.model_validate(user)
