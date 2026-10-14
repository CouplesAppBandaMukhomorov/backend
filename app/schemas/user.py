import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class UserRead(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": "e9d4fbcc-a250-4b76-a2fc-4dd5fd442fde",
                    "email": "ann@example.com",
                    "display_name": "Ann",
                    "avatar_url": "https://cdn.example.com/avatars/ann.png",
                    "created_at": "2026-10-13T11:43:15.622104Z",
                }
            ]
        },
    )

    id: uuid.UUID = Field(description="Идентификатор пользователя.")
    email: EmailStr = Field(description="Email аккаунта, он же логин.")
    display_name: str = Field(description="Отображаемое имя.")
    avatar_url: str | None = Field(
        default=None,
        description="Ссылка на аватар или `null`, если он не задан.",
    )
    created_at: datetime = Field(description="Момент регистрации.")


class UserShort(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": "e9d4fbcc-a250-4b76-a2fc-4dd5fd442fde",
                    "display_name": "Ann",
                    "avatar_url": None,
                }
            ]
        },
    )

    id: uuid.UUID = Field(description="Идентификатор пользователя.")
    display_name: str = Field(description="Отображаемое имя.")
    avatar_url: str | None = Field(
        default=None,
        description="Ссылка на аватар или `null`.",
    )


class UserUpdate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"display_name": "Ann Cooper"},
                {"avatar_url": None},
            ]
        }
    )

    display_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=120,
        description=(
            "Новое имя. Поле обязательное по смыслу: `null` вернёт `422`, а отсутствие поля "
            "в теле оставит имя без изменений."
        ),
        examples=["Ann Cooper"],
    )
    avatar_url: str | None = Field(
        default=None,
        max_length=1024,
        description=(
            "Новая ссылка на аватар. Передайте `null`, чтобы очистить аватар. "
            "Если поля нет в теле, оно не изменится."
        ),
        examples=["https://cdn.example.com/avatars/ann.png"],
    )

    @model_validator(mode="after")
    def reject_null_display_name(self) -> "UserUpdate":
        if self.display_name is None and "display_name" in self.model_fields_set:
            raise ValueError("'display_name' cannot be null")
        return self
