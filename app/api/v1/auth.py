from typing import Annotated

from fastapi import APIRouter, Body, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.openapi import error_response
from app.db.session import get_db
from app.schemas.auth import (
    GoogleLoginRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=TokenPair,
    status_code=status.HTTP_201_CREATED,
    summary="Зарегистрироваться по email",
    description=(
        "Создаёт аккаунт и сразу возвращает пару токенов, отдельный вызов входа не нужен. "
        "Пароль — от 8 до 128 символов.\n\n"
        "Создание аккаунта не создаёт пару: чтобы стать участником, нужно вызвать `POST /couples` "
        "или принять приглашение."
    ),
    responses={409: error_response("Email уже зарегистрирован. Код: `email_already_registered`.")},
)
async def register(
    payload: Annotated[
        RegisterRequest,
        Body(
            openapi_examples={
                "basic": {
                    "summary": "Обычная регистрация",
                    "value": {
                        "email": "ann@example.com",
                        "password": "supersecret",
                        "display_name": "Ann",
                    },
                }
            }
        ),
    ],
    db: AsyncSession = Depends(get_db),
) -> TokenPair:
    return await auth_service.register(db, payload)


@router.post(
    "/login",
    response_model=TokenPair,
    summary="Войти по email и паролю",
    description=(
        "Возвращает новую пару токенов.\n\n"
        "Если аккаунт создан через Google, пароля у него нет: такой вход вернёт `401` "
        "с кодом `invalid_credentials`. Для таких аккаунтов используйте `POST /auth/google`."
    ),
    responses={401: error_response("Неверный email или пароль. Код: `invalid_credentials`.")},
)
async def login(
    payload: Annotated[
        LoginRequest,
        Body(
            openapi_examples={
                "basic": {
                    "summary": "Обычный вход",
                    "value": {"email": "ann@example.com", "password": "supersecret"},
                }
            }
        ),
    ],
    db: AsyncSession = Depends(get_db),
) -> TokenPair:
    return await auth_service.login(db, payload)


@router.post(
    "/google",
    response_model=TokenPair,
    summary="Войти через Google",
    description=(
        "Принимает `id_token`, который фронт получает из Google Sign-In.\n\n"
        "Если аккаунта с таким email нет, он создаётся. Если аккаунт создан по паролю, "
        "Google-идентичность привяжется к нему, и пароль продолжит работать.\n\n"
        "Скоупы календаря здесь **не запрашиваются**: это только вход. Доступ к календарю "
        "подключается отдельно через `GET /google/connect`."
    ),
    responses={
        400: error_response(
            "`id_token` недействителен, истёк, выдан другому приложению или email не подтверждён. "
            "Коды: `invalid_google_token`, `google_email_not_verified`."
        ),
        500: error_response(
            "На бэкенде не задан `GOOGLE_CLIENT_ID`. Код: `google_login_not_configured`."
        ),
    },
)
async def login_with_google(
    payload: Annotated[
        GoogleLoginRequest,
        Body(
            openapi_examples={
                "basic": {
                    "summary": "Вход по id_token от Google Sign-In",
                    "value": {"id_token": "eyJhbGciOiJSUzI1NiIsImtpZCI6...<id_token>"},
                }
            }
        ),
    ],
    db: AsyncSession = Depends(get_db),
) -> TokenPair:
    return await auth_service.login_with_google(db, payload.id_token)


@router.post(
    "/refresh",
    response_model=TokenPair,
    summary="Обновить пару токенов",
    description=(
        "Принимает `refresh_token` и выдаёт новую пару.\n\n"
        "Вызывайте этот эндпоинт, когда любой другой запрос вернул `401` с кодом `invalid_token`, "
        "затем повторите исходный запрос с новым access-токеном.\n\n"
        "Отзыва токенов нет, поэтому старый refresh-токен остаётся валидным до истечения срока."
    ),
    responses={
        401: error_response(
            "Передан не refresh-токен либо он истёк и подпись не сходится. Код: `invalid_token`."
        )
    },
)
async def refresh(
    payload: Annotated[
        RefreshRequest,
        Body(
            openapi_examples={
                "basic": {
                    "summary": "Обновление по refresh-токену",
                    "value": {"refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...<refresh_token>"},
                }
            }
        ),
    ],
    db: AsyncSession = Depends(get_db),
) -> TokenPair:
    return await auth_service.refresh(db, payload.refresh_token)
