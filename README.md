# backend

Бэкенд приложения для пар: регистрация, пары 1:1, приглашения и общий календарь,
который работает поверх Google Calendar.

## Что умеет

- Регистрация и вход по email/паролю, а также вход через Google (`id_token`).
- JWT access + refresh токены.
- Пары один-к-одному: создание пары, приглашение по коду, принятие, выход. Оба партнёра
  имеют полные равные права.
- `together_since` у пары и вычисляемое `days_together` для фронта.
- Подключение Google-аккаунта через OAuth 2.0 (scope календаря, `access_type=offline`).
- Привязка существующего Google-календаря пары и CRUD событий в нём.
- События в базе **не хранятся**: источник правды — Google Calendar, данные читаются
  и пишутся по API в момент запроса.

## Стек

FastAPI, SQLAlchemy 2.0 (async) + asyncpg, Alembic, Pydantic v2, PostgreSQL, httpx,
PyJWT, argon2, cryptography (Fernet), pytest + respx.

## Быстрый старт (Docker)

```bash
cp .env.example .env
docker compose up --build
```

API будет доступен на `http://localhost:8000`, документация — на `http://localhost:8000/docs`.

Если `.env` уже есть, копировать не нужно. Локальный порт для PostgreSQL задаётся переменной
`POSTGRES_PORT` (по умолчанию `5432`): если порт занят другим Postgres, поставьте свободный
и приведите `DATABASE_URL` к тому же порту. В этом репозитории `.env` уже настроен на `55432`.

## Локальный запуск без Docker

Нужен запущенный PostgreSQL и переменная `DATABASE_URL`. Требуется Python 3.11+.

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

## Переменные окружения

| Переменная | Назначение |
|---|---|
| `APP_NAME` / `APP_VERSION` | название и версия, попадающие в OpenAPI |
| `DATABASE_URL` | DSN PostgreSQL, например `postgresql+asyncpg://couple:couple@localhost:5432/couple` |
| `POSTGRES_PORT` | порт, который публикует docker compose для базы |
| `JWT_SECRET` | секрет подписи JWT, обязательно заменить |
| `ACCESS_TOKEN_TTL_MINUTES` / `REFRESH_TOKEN_TTL_DAYS` | время жизни токенов |
| `FERNET_KEY` | ключ шифрования Google-токенов; если пусто — выводится из `JWT_SECRET` |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | креды OAuth-клиента Google |
| `GOOGLE_OAUTH_REDIRECT_URI` | redirect URI, должен совпадать с настройкой в Google Cloud |
| `GOOGLE_CALENDAR_API_BASE` | базовый URL Calendar API, полезно менять для E2E-тестов |
| `FRONTEND_REDIRECT_URL` | куда редиректить пользователя после Google OAuth |
| `INVITATION_TTL_DAYS` | срок жизни приглашения |
| `CORS_ORIGINS` | список origin через запятую |
| `API_SERVER_URL` | если задан, подставляется в `servers` OpenAPI; пусто — Swagger использует текущий origin |

Без `GOOGLE_CLIENT_ID` эндпоинт `POST /auth/google` отвечает ошибкой
`google_login_not_configured`: проверка `aud` у `id_token` обязательна, иначе был бы принят
токен от любого другого Google-приложения.

## Настройка Google Cloud

1. Открой [Google Cloud Console](https://console.cloud.google.com/) и создай проект.
2. **APIs & Services → Library** → найди **Google Calendar API** → **Enable**.
3. **APIs & Services → OAuth consent screen**:
   - тип **External**, заполни название и почту поддержки;
   - добавь scope `https://www.googleapis.com/auth/calendar.events` и
     `https://www.googleapis.com/auth/calendar.calendars.readonly`;
   - пока приложение в статусе **Testing**, добавь себя и тестировщиков в **Test users**.
4. **APIs & Services → Credentials → Create credentials → OAuth client ID**:
   - тип **Web application**;
   - **Authorized redirect URIs**: `http://localhost:8000/api/v1/google/callback`.
5. Скопируй `client_id` и `client_secret` в `.env`.

### Что важно знать про OAuth у Google

- **Логин через Google и доступ к календарю — два разных гранта.** Логин использует
  `id_token` со scope `openid email profile` и не запрашивает календарь. Календарь
  подключается отдельно через `GET /google/connect`.
- В статусе **Testing** refresh-токены живут **7 дней**, а количество тестировщиков
  ограничено 100 пользователями. Для продакшена нужна верификация приложения в Google
  (scope календаря относится к sensitive), иначе выход за эти лимиты невозможен.
- Наш бэкенд всегда пишет и читает календарь **токеном владельца календаря**, поэтому
  шаринг календаря внутри Google между партнёрами не требуется.

## API

Базовый префикс — `/api/v1`. Ошибки возвращаются в виде `{"detail": "...", "code": "..."}`.

### Auth

```
POST   /auth/register        {email, password, display_name} -> {access_token, refresh_token, ...}
POST   /auth/login           {email, password}
POST   /auth/google          {id_token}
POST   /auth/refresh         {refresh_token}
```

### Профиль

```
GET    /users/me
PATCH  /users/me             {display_name?, avatar_url?}
```

### Пара

```
POST   /couples              создать пару, создатель становится участником
GET    /couples/me           пара, участники, together_since, days_together, calendar
PATCH  /couples/me           {title?, timezone?, together_since?}
DELETE /couples/me           покинуть пару (пустая пара удаляется)
```

### Приглашения

```
POST   /invitations                  создать приглашение в свою пару -> {code, expires_at}
GET    /invitations/me               активное приглашение или null
GET    /invitations/{code}           превью приглашения
POST   /invitations/{code}/accept    вступить в пару
DELETE /invitations/{code}           отменить (только приглашающий)
```

### Google

```
GET    /google/connect        -> {authorization_url}
GET    /google/callback       обрабатывается Google, редиректит на FRONTEND_REDIRECT_URL
GET    /google/connection     статус подключения
DELETE /google/connection     отключить и отозвать токен
GET    /google/calendars      список календарей аккаунта (только с правом записи)
```

### Календарь пары

```
GET    /couple/calendar                         привязанный календарь или null
PUT    /couple/calendar                         {calendar_id}
DELETE /couple/calendar                         отвязать
GET    /couple/calendar/events                  ?time_min&time_max (по умолчанию сейчас .. +30 дней)
POST   /couple/calendar/events                  создать событие
GET    /couple/calendar/events/{event_id}
PATCH  /couple/calendar/events/{event_id}       частичное обновление
DELETE /couple/calendar/events/{event_id}
```

`time_min` и `time_max` — ISO 8601. Смещение передавайте через `Z` либо кодируйте `+` как
`%2B`: в query-строке сырой `+00:00` превращается в пробел и вызовет 422.

## Формат события

`event_id` — это идентификатор события в Google, отдельного хранилища нет.

Создание события:

```json
{
  "summary": "Ужин",
  "description": "Итальянский ресторан",
  "location": "ул. Пушкина, 1",
  "start": {"date_time": "2026-10-14T19:00:00+03:00", "time_zone": "Europe/Moscow"},
  "end": {"date_time": "2026-10-14T21:00:00+03:00", "time_zone": "Europe/Moscow"},
  "attendees": ["partner@example.com"],
  "reminders": {"use_default": true}
}
```

Событие на весь день — вместо `date_time` передаётся `date`:

```json
{
  "summary": "Годовщина",
  "start": {"date": "2026-06-01"},
  "end": {"date": "2026-06-02"}
}
```

Ответ содержит `is_all_day` и `recurring_event_id`, если событие из серии.
Если `time_zone` не указан, используется таймзона пары. Для наивного `date_time`
время интерпретируется в этой таймзоне; неизвестная таймзона приводит к фолбэку на UTC.

## Поведение, о котором стоит знать

- Привязывать календарь может любой партнёр, но календарь должен быть доступен на запись
  его Google-аккаунту. Read-only календари отклоняются с `calendar_not_writable`.
- Если пару покидает партнёр, чей аккаунт владел календарём, привязка снимается: оставшийся
  партнёр не продолжает работать через токен бывшего партнёра.
- `null` в `display_name` и `timezone` отклоняется (422) — это NOT NULL поля. `title` и
  `avatar_url` очистить через `null` можно.
- Конкурентные принятия одного приглашения сериализуются блокировкой строки пары, поэтому
  третьего участника появиться не может.

## Ограничения текущей версии

- Повторяющиеся события отдаются развёрнутыми (`singleEvents=true`), поэтому правки из
  приложения применяются к **конкретному вхождению** серии, а не ко всей серии.
- События в базе не кэшируются: `GET /events` каждый раз обращается к Google. Синхронизация
  происходит в момент запроса, вебхуков и поллинга нет.
- `PATCH` не умеет очищать поля (снять `description` или `location` нельзя, только заменить).
- Отзыва JWT нет: logout выполняется на клиенте удалением токенов.

## OpenAPI и документация

- `GET /docs` — Swagger UI, `GET /redoc` — ReDoc, `GET /openapi.json` — сама схема.
- В схеме описано то, что обычно и спрашивают: назначение каждой ручки, единый формат ошибок
  `{"detail", "code"}` с таблицей всех кодов, примеры тел запросов, описания каждого поля и
  пошаговые сценарии (подключение Google Calendar, приглашение в пару) в общем описании API.
- Все коды ошибок продублированы машинночитаемо в расширении `x-error-codes` у схемы
  `ErrorResponse` — удобно для генерации типов на фронте.
- Схема генерируется на лету, копии в репозитории нет, чтобы не разъезжались с кодом.
- Коды ошибок, перечисленные в `ERROR_CODES` в `app/api/openapi.py`, — единственный источник
  правды для таблицы в описании и для `x-error-codes`.
- `tests/test_openapi.py` валидирует схему по спецификации OpenAPI 3.1 и падает, если появится
  ручка без описания, параметр или поле без описания, примеров у тела запроса нет, схема ответа
  на ошибку не наша либо в коде появился код ошибки без документации.

## Разработка и тесты

```bash
pip install -e ".[dev]"
pytest
```

Тесты используют SQLite в памяти, внешние вызовы Google мокаются через respx, поэтому
реальная база и доступ в интернет не нужны.

## Миграции

```bash
alembic upgrade head
alembic revision --autogenerate -m "your change"
```
