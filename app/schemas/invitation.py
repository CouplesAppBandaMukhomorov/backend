import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.couple import CoupleRead
from app.schemas.user import UserShort

STATUS_FIELD = Field(
    description=(
        "Статус приглашения: `pending` — активно и можно принять, `accepted` — принято, "
        "`cancelled` — отменено автором, `expired` — истёк срок, `declined` — зарезервировано "
        "под отказ и пока не используется."
    ),
    examples=["pending"],
)


class InvitationRead(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": "84a8a689-4bb0-455b-b0d9-90c541445ad4",
                    "couple_id": "099bc611-969c-4626-92eb-8aa03b013cb2",
                    "code": "K9HAUV74",
                    "status": "pending",
                    "expires_at": "2026-10-20T11:43:15.654011Z",
                    "created_at": "2026-10-13T11:43:15.654357Z",
                    "inviter": {
                        "id": "e9d4fbcc-a250-4b76-a2fc-4dd5fd442fde",
                        "display_name": "Ann",
                        "avatar_url": None,
                    },
                    "invited_user": None,
                }
            ]
        }
    )

    id: uuid.UUID = Field(description="Идентификатор приглашения.")
    couple_id: uuid.UUID = Field(description="Пара, в которую приглашают.")
    code: str = Field(
        description=(
            "Короткий код из 8 символов для передачи партнёру. Проверяется без учёта регистра "
            "и действует 7 дней."
        ),
        examples=["K9HAUV74"],
    )
    status: str = STATUS_FIELD
    expires_at: datetime = Field(description="Момент, после которого код перестаёт работать.")
    created_at: datetime = Field(description="Момент создания приглашения.")
    inviter: UserShort = Field(description="Кто приглашает.")
    invited_user: UserShort | None = Field(
        default=None,
        description="Кто принял приглашение. `null`, пока приглашение не принято.",
    )


class InvitationPreview(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "code": "K9HAUV74",
                    "status": "pending",
                    "couple_id": "099bc611-969c-4626-92eb-8aa03b013cb2",
                    "couple_title": "Us",
                    "expires_at": "2026-10-20T11:43:15.654011Z",
                    "inviter": {
                        "id": "e9d4fbcc-a250-4b76-a2fc-4dd5fd442fde",
                        "display_name": "Ann",
                        "avatar_url": None,
                    },
                }
            ]
        }
    )

    code: str = Field(description="Код приглашения.", examples=["K9HAUV74"])
    status: str = STATUS_FIELD
    couple_id: uuid.UUID = Field(description="Пара, в которую приглашают.")
    couple_title: str | None = Field(
        default=None,
        description="Название пары, чтобы показать его на экране приглашения.",
        examples=["Us"],
    )
    expires_at: datetime = Field(description="Момент, после которого код перестаёт работать.")
    inviter: UserShort = Field(description="Кто приглашает.")


class InvitationAcceptResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "couple": {
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
                        "calendar": None,
                    }
                }
            ]
        }
    )

    couple: CoupleRead = Field(
        description="Пара после вступления: в `members` уже два участника. "
        "Отдельно запрашивать `GET /couples/me` не нужно."
    )
