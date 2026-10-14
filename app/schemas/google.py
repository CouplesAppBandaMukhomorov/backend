from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class GoogleAuthorizeUrl(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "authorization_url": "https://accounts.google.com/o/oauth2/v2/auth?client_id=...&scope=...&state=<подписанный state>"
                }
            ]
        }
    )

    authorization_url: str = Field(
        description=(
            "Ссылка на согласие Google. Открывайте её в системном браузере, ссылка подписана "
            "под текущего пользователя и живёт 10 минут."
        ),
    )


class GoogleConnectionRead(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "connected": True,
                    "scope": "https://www.googleapis.com/auth/calendar.events https://www.googleapis.com/auth/calendar.calendars.readonly",
                    "expires_at": "2026-10-13T12:43:50.641403Z",
                },
                {"connected": False, "scope": None, "expires_at": None},
            ]
        }
    )

    connected: bool = Field(
        description=(
            "`true`, если Google-аккаунт подключён и для него сохранены токены. "
            "`false` — обычное состояние, не ошибка."
        ),
        examples=[True],
    )
    scope: str | None = Field(
        default=None,
        description="Права, которые выдал пользователь. `null`, если аккаунт не подключён.",
    )
    expires_at: datetime | None = Field(
        default=None,
        description=(
            "Когда истекает сохранённый access-токен Google. Бэкенд обновляет его сам, "
            "поэтому фронту это поле нужно только для отладки."
        ),
    )


class GoogleCalendarRead(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": "abc123@group.calendar.google.com",
                    "summary": "Our calendar",
                    "description": None,
                    "timezone": "Europe/Moscow",
                    "access_role": "owner",
                    "primary": True,
                }
            ]
        }
    )

    id: str = Field(
        description="Идентификатор календаря. Именно его передавайте в `PUT /couple/calendar`.",
        examples=["abc123@group.calendar.google.com"],
    )
    summary: str = Field(
        description="Название календаря для интерфейса.",
        examples=["Our calendar"],
    )
    description: str | None = Field(
        default=None,
        description="Описание календаря, если оно задано.",
    )
    timezone: str | None = Field(
        default=None,
        description="Таймзона календаря по данным Google.",
        examples=["Europe/Moscow"],
    )
    access_role: str | None = Field(
        default=None,
        description=(
            "Права аккаунта на этот календарь. В этом списке попадаются `owner` и `writer`: "
            "календари только для чтения отфильтрованы."
        ),
        examples=["owner"],
    )
    primary: bool = Field(
        default=False,
        description="`true` для основного календаря аккаунта.",
        examples=[True],
    )
