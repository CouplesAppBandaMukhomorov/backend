# backend

Бэкенд приложения для пар: регистрация, пары 1:1, приглашения, общий календарь поверх
Google Calendar и общие заметки пары.

## Что умеет

- Регистрация и вход по email/паролю, а также вход через Google (`id_token`).
- JWT access + refresh токены.
- Пары один-к-одному: создание пары, приглашение по коду, принятие, выход. Оба партнёра
  имеют полные равные права.
- `together_since` у пары и вычисляемое `days_together` для фронта.
- Подключение Google-аккаунта через OAuth 2.0 (scope календаря, `access_type=offline`).
- Привязка существующего Google-календаря пары и CRUD событий в нём.
- Общие заметки пары: создание, чтение, изменение, удаление. Хранятся у нас в PostgreSQL,
  права у партнёров равные, доступны независимо от Google.
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
| `DATABASE_URL` | DSN PostgreSQL, например `postgresql+asyncpg://couple:couple@localhost:5432/couple`. В проде хост — не `localhost`, см. «Postgres на том же сервере» |
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

### Заметки

```
GET    /couple/notes                  ?limit&offset, закреплённые сверху, дальше по времени изменения
POST   /couple/notes                  {title?, content, pinned?}
GET    /couple/notes/{note_id}
PATCH  /couple/notes/{note_id}        {title?, content?, pinned?}
DELETE /couple/notes/{note_id}        204, безвозвратно
```

`title` необязателен, `content` обязателен. Пагинация через `limit` (по умолчанию 20,
максимум 100) и `offset`; конец списка — когда вернулось меньше, чем `limit`. Поля
`created_by` и `updated_by` показывают автора создания и последней правки.

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
- Заметки принадлежат паре, а не человеку: оба партнёра видят и меняют одни и те же заметки.
  Заголовок необязателен, `content` и `pinned` обязательны по смыслу — `null` в них даёт 422.
  Текст из одних пробелов тоже отклоняется (422), а заголовок обрезается по краям и из одних
  пробелов становится пустым.
- Когда пару распускают, её заметки удаляются вместе с ней. Если уходит один партнёр, а пара
  остаётся, заметки сохраняются.

## Ограничения текущей версии

- Повторяющиеся события отдаются развёрнутыми (`singleEvents=true`), поэтому правки из
  приложения применяются к **конкретному вхождению** серии, а не ко всей серии.
- События в базе не кэшируются: `GET /events` каждый раз обращается к Google. Синхронизация
  происходит в момент запроса, вебхуков и поллинга нет.
- `PATCH` не умеет очищать поля (снять `description` или `location` нельзя, только заменить).
- Отзыва JWT нет: logout выполняется на клиенте удалением токенов.
- Заметки удаляются безвозвратно, корзины нет. Список заметок сортируется по времени
  последнего изменения, поэтому правка поднимает заметку наверх и может сдвинуть границы
  страниц, пока список листают.

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

## CI/CD

Пайплайн `.github/workflows/ci-cd.yml` запускается на каждый push в `main` (и вручную через
`workflow_dispatch`). Три стейджа идут строго по очереди, каждый следующий стартует только
если предыдущий зелёный:

| Стейдж | Где выполняется | Что делает |
|---|---|---|
| `tests` | раннер GitHub | `pip install -e ".[dev]"` и `pytest` |
| `check migrations` | раннер GitHub | проверка, что в истории ровно одна head-ревизия, и рендер миграций в SQL (`alembic upgrade head --sql`). Сами миграции не применяются и прод-БД не трогается |
| `deploy` | сервер по SSH | `git fetch` и `checkout` проверенного коммита (`github.sha`), сборка `.env` из настроек окружения и запись его на сервер, `docker compose up -d --build --no-deps api`, затем health-check |

Деплоится **только контейнер приложения** (сервис `api` из `Dockerfile`), с флагом `--no-deps`:
база данных, сетевые и прочие сервисы пайплайном не поднимаются и не трогаются.
Поэтому в прод-`.env` обязателен `DATABASE_URL`, указывающий на реальную базу —
прод-override `docker-compose.prod.yml` подставляет его в контейнер вместо адреса
локального compose-сервиса `db`.

### Порядок применения миграций

Реальные миграции применяются **внутри контейнера при его старте**: в `docker-compose.yml` у
сервиса `api` команда `sh -c "alembic upgrade head && uvicorn …"`. Compose при
`up -d --build` сначала останавливает старый контейнер, и только затем новый применяет
миграции и поднимает uvicorn. Поэтому окна, в котором старый код работает с новой схемой,
не существует. Стейджи `check migrations`/`deploy` эту последовательность не разрывают:
`check migrations` ничего не меняет в прод-БД, а лишь валидирует миграции до деплоя.

Цена такого решения — короткий простой на время миграции: пока она выполняется, приложение
не обслуживает запросы. Если миграция упадёт, контейнер не стартует, а из-за
`restart: unless-stopped` уйдёт в цикл перезапусков (в логах деплоя это видно, health-check
падает).

Чтобы сократить простой до незаметного, миграции стоит держать обратно совместимыми
(expand/contract): в релизе N добавлять nullable-колонку или новую таблицу, а удаление
старой колонки делать отдельным релизом N+1. Тогда длительность миграции минимальна, а
предыдущая версия кода остаётся рабочей в любой момент переключения.

### Секреты и переменные

Настраиваются в **Settings → Secrets and variables → Actions**. Стейджу `deploy` назначено
окружение `production` (`environment: production`), поэтому всё заводим на уровне окружения:
тогда значения доступны только job-ам, нацеленным на прод, и их можно дополнительно закрыть
правилом *Required reviewers* и ограничением *Deployment branches*. Стейджи `tests` и
`check migrations` выполняются на раннере и никаких настроек не требуют.

В **secrets** идёт то, что действительно секрет: они маскируются в логах и не читаются обратно
в интерфейсе. В **variables** — всё остальное: значения видно, их удобнее отлаживать.

| Secret | Обязательный | Назначение |
|---|---|---|
| `SSH_PRIVATE_KEY` | да | приватный ключ для входа на сервер (совпадает с `~/.ssh/authorized_keys`) |
| `DATABASE_URL` | да | DSN боевой базы, вместе с паролем |
| `JWT_SECRET` | да | секрет подписи JWT |
| `FERNET_KEY` | да | ключ шифрования сохранённых Google-токенов |
| `GOOGLE_CLIENT_SECRET` | да | секрет OAuth-клиента Google |
| `SSH_HOST` | да | IP или домен сервера |
| `SSH_PORT` | да | SSH-порт сервера |
| `SSH_USER` | да | пользователь SSH |
| `DEPLOY_PATH` | да | абсолютный путь к клону репозитория на сервере |
| `HEALTHCHECK_URL` | да | URL проверки после деплоя, например `http://127.0.0.1:8000/health` |
| `SSH_KNOWN_HOSTS` | нет | зафиксировать host key сервера; если не задан, ключ подтягивается через `ssh-keyscan` |

| Variable | Обязательная | Назначение |
|---|---|---|
| `GOOGLE_CLIENT_ID` | да | идентификатор OAuth-клиента; публичный, он и так виден в ссылке на согласие Google |
| `GOOGLE_OAUTH_REDIRECT_URI` | да | redirect URI бэкенда, должен совпадать с настройкой в Google Cloud |
| `FRONTEND_REDIRECT_URL` | да | куда редиректить пользователя после согласия Google |
| `CORS_ORIGINS` | да | origin фронтенда через запятую |

Остальные настройки приложения (`APP_NAME`, `APP_VERSION`, `DEBUG`, TTL токенов,
`GOOGLE_CALENDAR_API_BASE`, `INVITATION_TTL_DAYS` и так далее) заводить не обязательно. Не
заданные просто не попадут в `.env`, и приложение возьмёт значения по умолчанию из
`app/core/config.py`. Полный список и признак «обязательно/опционально» живёт в
`scripts/render_env.sh`, а тест `tests/test_settings_env.py` следит, чтобы новая настройка не
потерялась.

`SSH_HOST`, `SSH_PORT`, `SSH_USER`, `DEPLOY_PATH`, `HEALTHCHECK_URL` формально не секреты, но
оставлены здесь, чтобы деплой продолжил работать без изменений. Перенести их в variables
можно, поправив в workflow `secrets.` на `vars.` — выигрыш только в том, что значения перестанут
маскироваться в логах.

Важно про `JWT_SECRET` и `FERNET_KEY`: в секреты нужно положить **текущие значения с сервера**,
а не сгенерированные заново. Новый `JWT_SECRET` вылогинит всех пользователей, а новый
`FERNET_KEY` сломает расшифровку сохранённых Google-токенов, и каждому пользователю придётся
подключать Google заново.

Ключ из `SSH_PRIVATE_KEY` — только для деплоя. Отдельный `GITHUB_TOKEN` не нужен: образ
никуда не публикуется, сборка идёт на сервере.

#### Правила значений настроек

`.env` читает не наш код, а Docker Compose, и у его парсера свои особенности. `scripts/render_env.sh`
подстраивается под них, чтобы значения доезжали до контейнера без искажений:

- **`$` экранируется как `$$`.** Если этого не сделать, Compose попытается подставить переменную
  и молча обрежет значение — причём кавычки не помогают. В готовом `.env` вы увидите `$$`, это
  нормально: Compose вернёт его обратно в один `$`.
- **Значение не должно начинаться с кавычки или `#`**, содержать пробел с последующей решёткой,
  иметь пробелы по краям или перевод строки. Compose такие значения обрежет или отвергнет,
  поэтому скрипт падает с понятной ошибкой **до** подключения к серверу, а не пишет битый файл.
- **Решётка внутри значения допустима**, если перед ней нет пробела: `p#ssword` доедет как есть,
  а `p # ssword` будет отклонено. Пробел в пароле закодируйте как `%20`.

Ошибка выглядит так:

```
render_env: cannot write DATABASE_URL to .env: the value contains a space followed by #, and compose treats the rest as a comment
```

### Что должно быть готово на сервере

1. Docker и Docker Compose v2.
2. Пользователь `SSH_USER` с доступом к Docker (член группы `docker`) и записанным публичным
   ключом в `~/.ssh/authorized_keys`.
3. Клон репозитория в `DEPLOY_PATH`. Сервер должен уметь читать приватный репозиторий —
   заведите read-only deploy key в **Settings → Deploy keys**. Ветка клона значения не имеет:
   пайплайн делает `git fetch` и переключается на конкретный коммит (`github.sha`), поэтому
   на прод попадает ровно тот код, который прошёл тесты.
4. `curl` для health-check.
5. PostgreSQL рядом с контейнером, на том же сервере. Его DSN кладётся в секрет `DATABASE_URL`,
   а как настроить сам Postgres — в разделе ниже.

`.env` в `DEPLOY_PATH` собирается пайплайном при каждом деплое: `scripts/render_env.sh` читает
настройки из окружения job-а и печатает файл, который затем уезжает на сервер. Руками его
заводить не нужно. Если обязательная настройка не задана в GitHub, деплой падает **до**
подключения к серверу, поэтому контейнер не может подняться с пустой конфигурацией. Файл
исключён из `git clean`, так что прод-настройки не затираются.

#### Postgres на том же сервере

База живёт нативно на хосте, а не в compose-проекте. Внутри контейнера `localhost` — это сам
контейнер, поэтому в DSN нужен адрес хоста:

```
DATABASE_URL=postgresql+asyncpg://couple:<пароль>@host.docker.internal:5432/couple
```

`host.docker.internal` в Linux-контейнере указывает на хост только если объявлен gateway. Это
уже сделано в `docker-compose.prod.yml`:

```yaml
    extra_hosts:
      - "host.docker.internal:host-gateway"
```

Проверить, что механизм работает именно на вашем сервере, можно так — он подставит тот же
самый адрес:

```bash
docker run --rm --add-host host.docker.internal:host-gateway alpine \
  nc -zv host.docker.internal 5432
```

**Пароль в DSN процентно кодируется.** SQLAlchemy декодирует percent-escapes, но `@` в
незакодированном виде ломает разбор молча: `couple:p@ss@host` разбирается как пароль `p` и
хост `ss@host`, и приложение уйдёт подключаться не туда. Поэтому `@` → `%40`, `:` → `%3A`,
`/` → `%2F`, `#` → `%23`, `%` → `%25`. `scripts/render_env.sh` падает, если в `DATABASE_URL`
больше одного `@`, и подсказывает замену.

Что нужно сделать на сервере один раз:

1. Роль и базу:

   ```bash
   sudo -u postgres psql -c "CREATE ROLE couple LOGIN PASSWORD '<пароль>';"
   sudo -u postgres psql -c "CREATE DATABASE couple OWNER couple;"
   ```

2. Разрешить подключения из docker-подсети. В `postgresql.conf`:

   ```
   listen_addresses = '*'
   ```

   В `pg_hba.conf` — строка под адрес шлюза compose-сети:

   ```
   host    all    all    172.16.0.0/12    scram-sha-256
   ```

   Точный адрес вашей сети:

   ```bash
   docker network inspect "$(basename "$PWD")_default" \
     --format '{{range .IPAM.Config}}{{.Gateway}}{{"\n"}}{{end}}'
   ```

   Затем `sudo systemctl reload postgresql`.

3. Если проверка из контейнера не проходит, посмотрите `ss -ltnp | grep 5432`: **Postgres должен
   слушать не только `127.0.0.1`**. Это самая частая причина.

Полезно знать: на macOS с Docker Desktop тот же контейнер достучится до хоста, даже если
Postgres слушает только `127.0.0.1`, — Docker Desktop проксирует loopback хоста через свой
внутренний адрес (`192.168.65.254`). На Linux `host-gateway` раскрывается в IP шлюза бриджа
(`172.17.0.1` и подобные), и такой listener отвечать не будет. То есть локальная проверка на
маке может скрыть проблему, которая проявится на сервере.

Compose-сервис `db` из `docker-compose.yml` в этом варианте не используется: деплой запускает
`up --no-deps api`, поэтому контейнер с базой не поднимается и пайплайн его не трогает.
