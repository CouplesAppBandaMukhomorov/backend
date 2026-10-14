import uuid
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_couple, get_current_user
from app.api.openapi import error_response
from app.db.session import get_db
from app.models.couple import Couple
from app.models.user import User
from app.schemas.note import NoteCreate, NoteRead, NoteUpdate
from app.services import note_service

router = APIRouter(prefix="/couple/notes", tags=["notes"])

COUPLE_NOT_FOUND = error_response(
    "Пользователь не состоит в паре, поэтому заметок у него нет. Код: `couple_not_found`."
)
NOTE_NOT_FOUND = error_response(
    "Заметка не найдена или принадлежит другой паре. Код: `note_not_found`."
)
NOTE_ID_PATH = Path(
    description="Идентификатор заметки из ответов `GET /couple/notes` или `POST /couple/notes`.",
    examples=["f0c1a3f2-6f1e-4b6e-9d5a-2c9a1b7e4d31"],
)
LIMIT_QUERY = Query(
    ge=1,
    le=100,
    description=(
        "Сколько заметок вернуть за один запрос, от 1 до 100. По умолчанию 20. "
        "Если пришло меньше заметок, чем `limit`, это последняя страница."
    ),
    examples=[20],
)
OFFSET_QUERY = Query(
    ge=0,
    description="Сколько заметок пропустить. Для второй страницы передайте `offset` = размер первой.",
    examples=[0],
)


@router.get(
    "",
    response_model=list[NoteRead],
    summary="Список заметок пары",
    description=(
        "Возвращает общие заметки пары. Доступ у обоих партнёров одинаковый.\n\n"
        "Порядок: сначала закреплённые, дальше по времени последнего изменения (свежие сверху), "
        "при совпадении времени — по идентификатору, чтобы порядок был предсказуемым.\n\n"
        "Постранично через `limit` и `offset`. Конец списка определяется по тому, что вернулось "
        "меньше заметок, чем `limit`. Общего количества заметок в ответе нет.\n\n"
        "Учтите: сортировка идёт по времени изменения, поэтому правка заметки поднимает её наверх "
        "и может сдвинуть границы страниц, пока вы листаете."
    ),
    responses={404: COUPLE_NOT_FOUND},
)
async def list_notes(
    limit: Annotated[int, LIMIT_QUERY] = 20,
    offset: Annotated[int, OFFSET_QUERY] = 0,
    couple: Couple = Depends(get_current_couple),
    db: AsyncSession = Depends(get_db),
) -> list[NoteRead]:
    notes = await note_service.list_notes(db, couple.id, limit, offset)
    return [NoteRead.model_validate(note) for note in notes]


@router.post(
    "",
    response_model=NoteRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать заметку",
    description=(
        "Создаёт общую заметку пары. Автором записывается текущий пользователь.\n\n"
        "Заголовок необязателен, текст — обязателен. Отдельного «приглашения» делиться заметкой "
        "не нужно: её сразу видит второй партнёр."
    ),
    responses={404: COUPLE_NOT_FOUND},
)
async def create_note(
    payload: Annotated[
        NoteCreate,
        Body(
            openapi_examples={
                "with_title": {
                    "summary": "Заметка с заголовком",
                    "value": {
                        "title": "Куда поехать летом",
                        "content": "Варианты: Португалия, Грузия, Алтай. Бюджет обсудить в марте.",
                    },
                },
                "quick": {
                    "summary": "Короткая заметка и сразу закрепить",
                    "value": {"content": "Забрать билеты в театр в пятницу", "pinned": True},
                },
            }
        ),
    ],
    couple: Couple = Depends(get_current_couple),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NoteRead:
    note = await note_service.create_note(db, couple, user, payload)
    return NoteRead.model_validate(note)


@router.get(
    "/{note_id}",
    response_model=NoteRead,
    summary="Получить заметку",
    description="Отдаёт одну заметку пары по идентификатору.",
    responses={404: error_response("Заметка не найдена или чужая. Коды: `note_not_found`, `couple_not_found`.")},
)
async def read_note(
    note_id: Annotated[uuid.UUID, NOTE_ID_PATH],
    couple: Couple = Depends(get_current_couple),
    db: AsyncSession = Depends(get_db),
) -> NoteRead:
    note = await note_service.load_note(db, couple.id, note_id)
    return NoteRead.model_validate(note)


@router.patch(
    "/{note_id}",
    response_model=NoteRead,
    summary="Изменить заметку",
    description=(
        "Частичное обновление: меняются только переданные поля.\n\n"
        "`title` можно очистить, передав `null`. `content` и `pinned` обязательны по смыслу: "
        "`null` в них вернёт `422`. Пустое тело вернёт `400` с кодом `empty_update`.\n\n"
        "После правки заметка помечается как изменённая текущим пользователем и поднимается "
        "в начало списка, если не закреплена."
    ),
    responses={
        400: error_response("В теле нет ни одного поля для изменения. Код: `empty_update`."),
        404: error_response("Заметка не найдена или чужая. Коды: `note_not_found`, `couple_not_found`."),
    },
)
async def update_note(
    note_id: Annotated[uuid.UUID, NOTE_ID_PATH],
    payload: Annotated[
        NoteUpdate,
        Body(
            openapi_examples={
                "content": {"summary": "Обновить текст", "value": {"content": "Билеты смотреть в апреле."}},
                "pin": {"summary": "Закрепить", "value": {"pinned": True}},
                "clear_title": {"summary": "Убрать заголовок", "value": {"title": None}},
            }
        ),
    ],
    couple: Couple = Depends(get_current_couple),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NoteRead:
    note = await note_service.update_note(db, couple.id, note_id, user, payload)
    return NoteRead.model_validate(note)


@router.delete(
    "/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить заметку",
    description=(
        "Удаляет заметку навсегда: корзины и восстановления нет. Тело ответа пустое.\n\n"
        "Удалить может любой из партнёров, авторство не проверяется."
    ),
    responses={
        404: error_response("Заметка не найдена или чужая. Коды: `note_not_found`, `couple_not_found`."),
    },
)
async def delete_note(
    note_id: Annotated[uuid.UUID, NOTE_ID_PATH],
    couple: Couple = Depends(get_current_couple),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await note_service.delete_note(db, couple.id, note_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
