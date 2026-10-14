import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.user import UserShort

CONTENT_MAX_LENGTH = 20000


def _reject_blank_content(value: str | None) -> str | None:
    if value is not None and not value.strip():
        raise ValueError("'content' cannot be blank")
    return value


def _normalize_title(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip() or None


class NoteCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "title": "Куда поехать летом",
                    "content": "Варианты: Португалия, Грузия, Алтай. Бюджет обсудить в марте.",
                },
                {"content": "Забрать билеты в театр в пятницу", "pinned": True},
            ]
        }
    )

    title: str | None = Field(
        default=None,
        max_length=200,
        description=(
            "Заголовок заметки. Необязателен: можно писать короткие заметки только с текстом. "
            "Пробелы по краям обрезаются, заголовок из одних пробелов превращается в `null`."
        ),
        examples=["Куда поехать летом"],
    )
    content: str = Field(
        min_length=1,
        max_length=CONTENT_MAX_LENGTH,
        description=(
            f"Текст заметки, от 1 до {CONTENT_MAX_LENGTH} символов, только текст без форматирования. "
            "Внутренние переносы и отступы сохраняются как есть, но строка из одних пробелов "
            "не принимается: вернётся `422`."
        ),
        examples=["Варианты: Португалия, Грузия, Алтай."],
    )
    pinned: bool = Field(
        default=False,
        description="Закрепить заметку: закреплённые всегда идут в начале списка.",
        examples=[False],
    )

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str | None) -> str | None:
        return _normalize_title(value)

    @field_validator("content")
    @classmethod
    def reject_blank_content(cls, value: str) -> str:
        return _reject_blank_content(value)


class NoteUpdate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"content": "Варианты: Португалия, Грузия, Алтай. Билеты смотреть в апреле."},
                {"pinned": True},
                {"title": None},
            ]
        }
    )

    title: str | None = Field(
        default=None,
        max_length=200,
        description=(
            "Новый заголовок. Передайте `null`, чтобы убрать заголовок. Отсутствие поля — без изменений. "
            "Пробелы по краям обрезаются, заголовок из одних пробелов тоже убирает заголовок."
        ),
        examples=["Куда поехать летом"],
    )
    content: str | None = Field(
        default=None,
        min_length=1,
        max_length=CONTENT_MAX_LENGTH,
        description=(
            f"Новый текст заметки, от 1 до {CONTENT_MAX_LENGTH} символов. "
            "Обязательное по смыслу поле: `null` вернёт `422`, как и строка из одних пробелов. "
            "Отсутствие поля — без изменений."
        ),
        examples=["Варианты: Португалия, Грузия, Алтай. Билеты смотреть в апреле."],
    )
    pinned: bool | None = Field(
        default=None,
        description=(
            "Закрепить или открепить заметку. Обязательное по смыслу поле: `null` вернёт `422`. "
            "Отсутствие поля — без изменений."
        ),
        examples=[True],
    )

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str | None) -> str | None:
        return _normalize_title(value)

    @field_validator("content")
    @classmethod
    def reject_blank_content(cls, value: str | None) -> str | None:
        return _reject_blank_content(value)

    @model_validator(mode="after")
    def reject_explicit_nulls(self) -> "NoteUpdate":
        for name in ("content", "pinned"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"'{name}' cannot be null")
        return self


class NoteRead(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": "f0c1a3f2-6f1e-4b6e-9d5a-2c9a1b7e4d31",
                    "title": "Куда поехать летом",
                    "content": "Варианты: Португалия, Грузия, Алтай. Бюджет обсудить в марте.",
                    "pinned": False,
                    "created_by": {
                        "id": "e9d4fbcc-a250-4b76-a2fc-4dd5fd442fde",
                        "display_name": "Ann",
                        "avatar_url": None,
                    },
                    "updated_by": {
                        "id": "d11ff450-74f2-4d6a-a4d2-fedf3dc89210",
                        "display_name": "Bob",
                        "avatar_url": None,
                    },
                    "created_at": "2026-10-14T09:12:03.114021Z",
                    "updated_at": "2026-10-14T18:40:55.902113Z",
                }
            ]
        }
    )

    id: uuid.UUID = Field(description="Идентификатор заметки. Используйте его в `GET`, `PATCH` и `DELETE`.")
    title: str | None = Field(
        default=None,
        description="Заголовок или `null`, если его нет. Заметка без заголовка — нормальное состояние.",
        examples=["Куда поехать летом"],
    )
    content: str = Field(
        description="Текст заметки.",
        examples=["Варианты: Португалия, Грузия, Алтай."],
    )
    pinned: bool = Field(
        description="Закреплена ли заметка.",
        examples=[False],
    )
    created_by: UserShort = Field(
        description="Кто создал заметку. Оба партнёра равны в правах, но автор виден.",
    )
    updated_by: UserShort = Field(
        description="Кто последним изменил заметку. Меняется при каждом `PATCH`, включая смену `pinned`.",
    )
    created_at: datetime = Field(description="Когда заметка создана.")
    updated_at: datetime = Field(
        description=(
            "Когда заметку последний раз меняли. По этому полю идёт сортировка списка, "
            "поэтому правка поднимает заметку наверх."
        ),
    )
