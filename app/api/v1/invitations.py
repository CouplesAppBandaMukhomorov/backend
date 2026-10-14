from typing import Annotated

from fastapi import APIRouter, Depends, Path, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.openapi import error_response
from app.db.session import get_db
from app.models.user import User
from app.schemas.invitation import (
    InvitationAcceptResponse,
    InvitationPreview,
    InvitationRead,
)
from app.services import invitation_service

router = APIRouter(prefix="/invitations", tags=["invitations"])

CODE_PATH = Path(
    description="Код приглашения из `POST /invitations`, например `K9HAUV74`. Регистр не важен.",
    examples=["K9HAUV74"],
)


@router.post(
    "",
    response_model=InvitationRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать приглашение партнёра",
    description=(
        "Создаёт приглашение в пару текущего пользователя и возвращает короткий код.\n\n"
        "- Код действует 7 дней.\n"
        "- Активное приглашение в паре всегда одно: создание нового отменяет предыдущее.\n"
        "- Приглашать можно, пока в паре меньше двух участников.\n"
        "- Код нужно передать партнёру любым способом, бэкенд сам его никуда не отправляет.\n\n"
        "Текущее активное приглашение возвращает `GET /invitations/me`."
    ),
    responses={
        409: error_response(
            "Сначала нужно создать пару (`couple_required`), либо в паре уже два участника (`couple_is_full`)."
        ),
    },
)
async def create_invitation(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvitationRead:
    return await invitation_service.create_invitation(db, user)


@router.get(
    "/me",
    response_model=InvitationRead | None,
    summary="Получить активное приглашение",
    description=(
        "Возвращает активное приглашение пары, чтобы показать экран «ждём партнёра», "
        "либо `null`, если активного приглашения нет.\n\n"
        "`null` приходит и тогда, когда пользователь вообще не состоит в паре, — это не ошибка, "
        "отдельного `404` здесь нет.\n\n"
        "Просроченное приглашение помечается как `expired` и тоже даёт `null`."
    ),
)
async def read_active_invitation(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvitationRead | None:
    return await invitation_service.get_active_invitation(db, user)


@router.get(
    "/{code}",
    response_model=InvitationPreview,
    summary="Посмотреть приглашение по коду",
    description=(
        "Превью перед принятием: кто приглашает, в какую пару и до какого числа действует код. "
        "Вызывать можно ещё до вступления в пару, нужен только свой access-токен.\n\n"
        "Если срок истёк, статус вернётся как `expired`, отдельной ошибки не будет."
    ),
    responses={
        404: error_response("Приглашение с таким кодом не найдено. Код: `invitation_not_found`."),
    },
)
async def read_invitation(
    code: Annotated[str, CODE_PATH],
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvitationPreview:
    return await invitation_service.get_preview(db, code)


@router.post(
    "/{code}/accept",
    response_model=InvitationAcceptResponse,
    summary="Принять приглашение и вступить в пару",
    description=(
        "Добавляет текущего пользователя в пару по коду и возвращает пару с двумя участниками.\n\n"
        "Ограничения: нельзя принять своё приглашение, нельзя вступить, уже состоя в другой паре, "
        "и нельзя стать третьим участником.\n\n"
        "Повторный вызов с тем же кодом вернёт `409` с кодом `invitation_not_active`: "
        "приглашение уже использовано."
    ),
    responses={
        400: error_response("Попытка принять собственное приглашение. Код: `cannot_accept_own_invitation`."),
        404: error_response("Приглашение с таким кодом не найдено. Код: `invitation_not_found`."),
        409: error_response(
            "Приглашение неактивно или просрочено, пользователь уже в паре либо она заполнена. "
            "Коды: `invitation_not_active`, `invitation_expired`, `already_in_couple`, `couple_is_full`."
        ),
    },
)
async def accept_invitation(
    code: Annotated[str, CODE_PATH],
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvitationAcceptResponse:
    return await invitation_service.accept_invitation(db, user, code)


@router.delete(
    "/{code}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Отменить приглашение",
    description=(
        "Отменяет приглашение. Доступно только тому, кто его создал, — остальным `403`.\n\n"
        "После отмены `GET /invitations/me` вернёт `null`, а код нельзя будет принять. "
        "Идемпотентно: повторная отмена уже отменённого приглашения отвечает `204`."
    ),
    responses={
        403: error_response("Отменяет не автор приглашения. Код: `not_inviter`."),
        404: error_response("Приглашение с таким кодом не найдено. Код: `invitation_not_found`."),
    },
)
async def cancel_invitation(
    code: Annotated[str, CODE_PATH],
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await invitation_service.cancel_invitation(db, user, code)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
