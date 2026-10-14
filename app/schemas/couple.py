import uuid
from datetime import date as DateType
from datetime import datetime as DateTimeType

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.calendar import CalendarLink
from app.schemas.user import UserShort


class CoupleCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {},
                {"title": "Us", "together_since": "2024-02-14", "timezone": "Europe/Moscow"},
            ]
        }
    )

    title: str | None = Field(
        default=None,
        max_length=120,
        description="Название пары для интерфейса. Можно задать позже.",
        examples=["Us"],
    )
    timezone: str = Field(
        default="UTC",
        max_length=64,
        description=(
            "Таймзона пары в формате IANA. Используется как таймзона по умолчанию для новых "
            "событий и подставляется, когда `time_zone` не указан в самом событии."
        ),
        examples=["Europe/Moscow"],
    )
    together_since: DateType | None = Field(
        default=None,
        description=(
            "Дата начала отношений. Из неё считается `days_together`, чтобы фронт мог "
            "показать «вместе уже N дней»."
        ),
        examples=["2024-02-14"],
    )


class CoupleUpdate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"together_since": "2024-02-14", "timezone": "Europe/Moscow"},
                {"title": "Our story"},
            ]
        }
    )

    title: str | None = Field(
        default=None,
        max_length=120,
        description="Новое название пары. Передайте `null`, чтобы очистить. Отсутствие поля — без изменений.",
        examples=["Our story"],
    )
    timezone: str | None = Field(
        default=None,
        max_length=64,
        description=(
            "Новая таймзона пары. Обязательное по смыслу поле: `null` вернёт `422`. "
            "Отсутствие поля — без изменений."
        ),
        examples=["Europe/Moscow"],
    )
    together_since: DateType | None = Field(
        default=None,
        description="Новая дата начала отношений. Передайте `null`, чтобы очистить.",
        examples=["2024-02-14"],
    )

    @model_validator(mode="after")
    def reject_null_timezone(self) -> "CoupleUpdate":
        if self.timezone is None and "timezone" in self.model_fields_set:
            raise ValueError("'timezone' cannot be null")
        return self


class CoupleRead(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": "099bc611-969c-4626-92eb-8aa03b013cb2",
                    "title": "Us",
                    "timezone": "Europe/Moscow",
                    "together_since": "2024-02-14",
                    "days_together": 972,
                    "created_at": "2026-10-13T11:43:15.622104Z",
                    "members": [
                        {
                            "id": "e9d4fbcc-a250-4b76-a2fc-4dd5fd442fde",
                            "display_name": "Ann",
                            "avatar_url": None,
                        },
                        {
                            "id": "d11ff450-74f2-4d6a-a4d2-fedf3dc89210",
                            "display_name": "Bob",
                            "avatar_url": None,
                        },
                    ],
                    "calendar": {
                        "calendar_id": "abc123@group.calendar.google.com",
                        "summary": "Our calendar",
                        "owner_id": "e9d4fbcc-a250-4b76-a2fc-4dd5fd442fde",
                    },
                }
            ]
        }
    )

    id: uuid.UUID = Field(description="Идентификатор пары.")
    title: str | None = Field(default=None, description="Название пары или `null`.")
    timezone: str = Field(
        description="Таймзона пары, она же значение по умолчанию для новых событий.",
        examples=["Europe/Moscow"],
    )
    together_since: DateType | None = Field(
        default=None,
        description="Дата начала отношений или `null`, если ещё не указана.",
    )
    days_together: int | None = Field(
        default=None,
        description=(
            "Сколько дней пара вместе на сегодня, считается по `together_since`. "
            "`null`, если дата не задана. Значение готово для показа, считать на фронте не нужно."
        ),
        examples=[972],
    )
    created_at: DateTimeType = Field(description="Момент создания пары.")
    members: list[UserShort] = Field(
        description="Участники пары: один, пока партнёр не принял приглашение, затем два. "
        "Отсортированы по времени вступления.",
    )
    calendar: CalendarLink | None = Field(
        default=None,
        description="Привязанный Google-календарь или `null`, если он ещё не привязан.",
    )
