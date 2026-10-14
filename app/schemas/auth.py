from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr = Field(
        description="Email нового аккаунта. Он же логин, поэтому должен быть уникальным.",
        examples=["ann@example.com"],
    )
    password: str = Field(
        min_length=8,
        max_length=128,
        description="Пароль от 8 до 128 символов.",
        examples=["supersecret"],
    )
    display_name: str = Field(
        min_length=1,
        max_length=120,
        description="Отображаемое имя, его увидят партнёр и другие пользователи в паре.",
        examples=["Ann"],
    )


class LoginRequest(BaseModel):
    email: EmailStr = Field(description="Email аккаунта.", examples=["ann@example.com"])
    password: str = Field(
        min_length=1,
        max_length=128,
        description="Пароль. Для аккаунта, созданного через Google, пароля нет.",
        examples=["supersecret"],
    )


class GoogleLoginRequest(BaseModel):
    id_token: str = Field(
        min_length=1,
        description="`id_token` из Google Sign-In. Календарные права здесь не нужны.",
        examples=["eyJhbGciOiJSUzI1NiIsImtpZCI6...<id_token>"],
    )


class RefreshRequest(BaseModel):
    refresh_token: str = Field(
        min_length=1,
        description="`refresh_token` из предыдущего ответа `TokenPair`.",
        examples=["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...<refresh_token>"],
    )


class TokenPair(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...<access_token>",
                    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...<refresh_token>",
                    "token_type": "bearer",
                    "expires_in": 1800,
                }
            ]
        }
    )

    access_token: str = Field(
        description="JWT для заголовка `Authorization: Bearer <access_token>`. Живёт 30 минут.",
    )
    refresh_token: str = Field(
        description="JWT для `POST /auth/refresh`. Живёт 30 дней.",
    )
    token_type: str = Field(
        default="bearer",
        description="Всегда `bearer`.",
        examples=["bearer"],
    )
    expires_in: int = Field(
        description="Срок жизни `access_token` в секундах. При значениях по умолчанию — 1800.",
        examples=[1800],
    )
