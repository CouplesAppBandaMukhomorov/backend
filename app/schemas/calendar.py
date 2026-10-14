import uuid
from datetime import date as DateType
from datetime import datetime as DateTimeType

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CalendarLinkRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"calendar_id": "abc123@group.calendar.google.com"}]
        }
    )

    calendar_id: str = Field(
        min_length=1,
        max_length=255,
        description=(
            "Идентификатор календаря из `GET /google/calendars`. Годится только календарь, "
            "доступный на запись подключённому Google-аккаунту."
        ),
        examples=["abc123@group.calendar.google.com"],
    )


class CalendarLink(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "calendar_id": "abc123@group.calendar.google.com",
                    "summary": "Our calendar",
                    "owner_id": "e9d4fbcc-a250-4b76-a2fc-4dd5fd442fde",
                }
            ]
        }
    )

    calendar_id: str = Field(
        description="Идентификатор привязанного календаря в Google.",
        examples=["abc123@group.calendar.google.com"],
    )
    summary: str | None = Field(
        default=None,
        description="Название календаря на момент привязки.",
        examples=["Our calendar"],
    )
    owner_id: uuid.UUID = Field(
        description=(
            "Пользователь, чьим Google-аккаунтом читается и пишется этот календарь. "
            "Именно он должен был пройти `GET /google/connect`."
        ),
    )


class EventDateTime(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"date": None, "date_time": "2026-10-14T19:00:00+03:00", "time_zone": "Europe/Moscow"},
                {"date": "2026-06-01", "date_time": None, "time_zone": None},
            ]
        }
    )

    date: DateType | None = Field(
        default=None,
        description=(
            "Дата для события на весь день, `YYYY-MM-DD`. Взаимоисключающе с `date_time`: "
            "передавайте ровно одно из этих полей. Для `end` помните, что дата исключающая."
        ),
        examples=["2026-06-01"],
    )
    date_time: DateTimeType | None = Field(
        default=None,
        description=(
            "Момент времени для обычного события, ISO 8601. Взаимоисключающе с `date`. "
            "Если смещение не указано, время трактуется в таймзоне из `time_zone` "
            "или в таймзоне пары."
        ),
        examples=["2026-10-14T19:00:00+03:00"],
    )
    time_zone: str | None = Field(
        default=None,
        description=(
            "Таймзона IANA для этого события. Если не указана, используется таймзона пары, "
            "а неизвестное значение приводит к фолбэку на UTC."
        ),
        examples=["Europe/Moscow"],
    )


class EventReminders(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"use_default": True, "overrides": None},
                {"use_default": False, "overrides": [{"method": "popup", "minutes": 30}]},
            ]
        }
    )

    use_default: bool | None = Field(
        default=None,
        description=(
            "Использовать напоминания по умолчанию из Google Calendar. "
            "Передайте `false`, если задаёте свои в `overrides`."
        ),
        examples=[True],
    )
    overrides: list[dict] | None = Field(
        default=None,
        description=(
            "Свои напоминания Google в исходном формате: `method` (`email` или `popup`) "
            "и `minutes` (за сколько минут)."
        ),
        examples=[[{"method": "popup", "minutes": 30}]],
    )


class EventBase(BaseModel):
    summary: str | None = Field(
        default=None,
        max_length=1024,
        description="Название события. Для создания обязательно.",
        examples=["Ужин"],
    )
    description: str | None = Field(
        default=None,
        description="Описание события. При `PATCH` можно только заменить, очистить нельзя.",
        examples=["Итальянский ресторан"],
    )
    location: str | None = Field(
        default=None,
        description="Место события. При `PATCH` можно только заменить, очистить нельзя.",
        examples=["ул. Пушкина, 1"],
    )
    start: EventDateTime | None = Field(
        default=None,
        description="Начало события. Обязательно при создании.",
    )
    end: EventDateTime | None = Field(
        default=None,
        description=(
            "Окончание события. Обязательно при создании. Для события на весь день "
            "`end.date` должен быть следующим днём: Google трактует её как исключающую."
        ),
    )
    reminders: EventReminders | None = Field(
        default=None,
        description="Напоминания Google. Если не передать, сработают настройки Google по умолчанию.",
    )
    attendees: list[str] | None = Field(
        default=None,
        description=(
            "Email участников. Google разошлёт им приглашения и покажет событие в их календарях. "
            "Достаточно email партнёра."
        ),
        examples=[["partner@example.com"]],
    )
    color_id: str | None = Field(
        default=None,
        description=(
            "Цвет события в палитре Google Calendar, идентификатор от `1` до `11`. "
            "Соответствие цветов смотрите в документации Google."
        ),
        examples=["7"],
    )


class EventCreate(EventBase):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "summary": "Ужин",
                    "description": "Итальянский ресторан",
                    "location": "ул. Пушкина, 1",
                    "start": {"date_time": "2026-10-14T19:00:00+03:00", "time_zone": "Europe/Moscow"},
                    "end": {"date_time": "2026-10-14T21:00:00+03:00", "time_zone": "Europe/Moscow"},
                    "attendees": ["partner@example.com"],
                    "reminders": {"use_default": True},
                },
                {
                    "summary": "Годовщина",
                    "start": {"date": "2026-06-01"},
                    "end": {"date": "2026-06-02"},
                },
            ]
        }
    )

    summary: str = Field(
        min_length=1,
        max_length=1024,
        description="Название события, обязательное поле.",
        examples=["Ужин"],
    )
    start: EventDateTime = Field(description="Начало: ровно одно из `date` или `date_time`.")
    end: EventDateTime = Field(
        description=(
            "Окончание: ровно одно из `date` или `date_time`. Для события на весь день "
            "укажите следующий день, иначе Google вернёт ошибку."
        )
    )

    @model_validator(mode="after")
    def validate_times(self) -> "EventCreate":
        for name in ("start", "end"):
            value = getattr(self, name)
            if (value.date is None) == (value.date_time is None):
                raise ValueError(f"'{name}' must define exactly one of 'date' or 'date_time'")
        return self


class EventUpdate(EventBase):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "summary": "Ужин перенесён",
                    "start": {"date_time": "2026-10-15T20:00:00+03:00", "time_zone": "Europe/Moscow"},
                    "end": {"date_time": "2026-10-15T22:00:00+03:00", "time_zone": "Europe/Moscow"},
                },
                {"location": "ул. Ленина, 5"},
            ]
        }
    )

    @model_validator(mode="after")
    def validate_times(self) -> "EventUpdate":
        for name in ("start", "end"):
            value = getattr(self, name)
            if value is None:
                continue
            if (value.date is None) == (value.date_time is None):
                raise ValueError(f"'{name}' must define exactly one of 'date' or 'date_time'")
        return self


class EventRead(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": "6k3vk8bq1abc",
                    "summary": "Ужин",
                    "description": "Итальянский ресторан",
                    "location": "ул. Пушкина, 1",
                    "start": {"date": None, "date_time": "2026-10-14T19:00:00+03:00", "time_zone": "Europe/Moscow"},
                    "end": {"date": None, "date_time": "2026-10-14T21:00:00+03:00", "time_zone": "Europe/Moscow"},
                    "is_all_day": False,
                    "status": "confirmed",
                    "html_link": "https://calendar.google.com/event?eid=6k3vk8bq1abc",
                    "recurring_event_id": None,
                    "attendees": ["partner@example.com"],
                    "updated": "2026-10-01T10:00:00Z",
                },
                {
                    "id": "base123_20260601T160000Z",
                    "summary": "Годовщина",
                    "description": None,
                    "location": None,
                    "start": {"date": "2026-06-01", "date_time": None, "time_zone": None},
                    "end": {"date": "2026-06-02", "date_time": None, "time_zone": None},
                    "is_all_day": True,
                    "status": "confirmed",
                    "html_link": "https://calendar.google.com/event?eid=base123",
                    "recurring_event_id": "base123",
                    "attendees": None,
                    "updated": "2026-10-01T10:00:00Z",
                },
            ]
        }
    )

    id: str = Field(
        description=(
            "Идентификатор события в Google. Для события из серии это идентификатор конкретного "
            "вхождения. Передавайте как есть в `GET`, `PATCH` и `DELETE`."
        ),
        examples=["6k3vk8bq1abc"],
    )
    summary: str | None = Field(default=None, description="Название события.", examples=["Ужин"])
    description: str | None = Field(default=None, description="Описание события.")
    location: str | None = Field(default=None, description="Место события.")
    start: EventDateTime = Field(description="Начало события.")
    end: EventDateTime = Field(description="Окончание события.")
    is_all_day: bool = Field(
        description=(
            "`true`, если событие на весь день. Признак посчитан на бэкенде: смотрите на него, "
            "а не на `start.date`, чтобы не разбирать два варианта формата."
        ),
        examples=[False],
    )
    status: str | None = Field(
        default=None,
        description=(
            "Статус события в Google. В списках всегда `confirmed`: отменённые события "
            "отфильтрованы."
        ),
        examples=["confirmed"],
    )
    html_link: str | None = Field(
        default=None,
        description="Ссылка на событие в веб-интерфейсе Google Calendar. Можно открыть наружу.",
    )
    recurring_event_id: str | None = Field(
        default=None,
        description=(
            "Для события из серии — идентификатор базового повторяющегося события. "
            "`null` для одиночного события. Правки применяются только к текущему вхождению."
        ),
    )
    attendees: list[str] | None = Field(
        default=None,
        description="Email участников события. `null`, если участников нет.",
        examples=[["partner@example.com"]],
    )
    updated: DateTimeType | None = Field(
        default=None,
        description=(
            "Когда событие последний раз менялось в Google. Удобно для инвалидации кэша "
            "на фронте, если он у вас будет."
        ),
    )
