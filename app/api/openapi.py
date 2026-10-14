from copy import deepcopy

from fastapi import FastAPI
from pydantic.json_schema import models_json_schema

from app.schemas.errors import ErrorResponse, ValidationErrorResponse

ERROR_CODES: dict[str, tuple[int, str]] = {
    "invalid_credentials": (401, "Неверный email или пароль либо у аккаунта нет пароля, потому что он создан через Google."),
    "missing_token": (401, "Заголовок `Authorization` не передан."),
    "invalid_token": (401, "Access-токен повреждён, истёк или передан не тот тип токена (например, refresh вместо access)."),
    "invalid_oauth_state": (401, "Подписанный `state` в Google OAuth недействителен или истёк. Нужно заново начать подключение через `GET /google/connect`."),
    "not_inviter": (403, "Отменить приглашение может только тот, кто его создал."),
    "google_access_denied": (403, "Google отказал в доступе: права отозваны пользователем или недостаточны для операции."),
    "invalid_google_token": (400, "Google `id_token` недействителен, истёк или выдан для другого приложения."),
    "google_email_not_verified": (400, "Email в Google-аккаунте не подтверждён, вход отклонён."),
    "cannot_accept_own_invitation": (400, "Нельзя принять собственное приглашение."),
    "calendar_not_available": (400, "Календарь недоступен подключённому Google-аккаунту."),
    "calendar_not_writable": (400, "Календарь доступен только для чтения, привязать его нельзя."),
    "empty_update": (400, "В `PATCH` не передано ни одного поля для изменения."),
    "invalid_time_range": (400, "`time_max` не больше `time_min`."),
    "invalid_event_time": (400, "Не удалось собрать время события: не задан ни `date`, ни `date_time`."),
    "couple_not_found": (404, "Пользователь не состоит в паре, поэтому пара недоступна."),
    "not_in_couple": (404, "Попытка выйти из пары, но пользователь в ней не состоит."),
    "invitation_not_found": (404, "Приглашение с таким кодом не найдено."),
    "calendar_not_found": (404, "Календарь или событие не найдены в Google: удалены либо недоступны аккаунту."),
    "email_already_registered": (409, "Email уже зарегистрирован."),
    "already_in_couple": (409, "Пользователь уже состоит в паре: создание второй пары или принятие ещё одного приглашения невозможно."),
    "couple_required": (409, "Сначала нужно создать пару, чтобы приглашать партнёра."),
    "couple_is_full": (409, "В паре уже два участника."),
    "invitation_not_active": (409, "Приглашение уже принято, отменено или просрочено."),
    "invitation_expired": (409, "Срок действия приглашения истёк."),
    "google_not_connected": (409, "Google-аккаунт не подключён, сначала нужно пройти `GET /google/connect`."),
    "google_reconnect_required": (409, "Google-аккаунт нужно подключить заново: refresh-токен отсутствует либо отозван."),
    "calendar_not_linked": (409, "К паре пока не привязан Google-календарь."),
    "google_login_not_configured": (500, "На бэкенде не задан `GOOGLE_CLIENT_ID`, вход через Google недоступен."),
    "token_decryption_failed": (500, "Сохранённый Google-токен не удалось расшифровать: сменился `FERNET_KEY` или `JWT_SECRET`. Нужно подключить Google заново."),
    "google_api_error": (502, "Google Calendar API вернул ошибку. Текст ошибки Google приходит в поле `detail`."),
    "validation_error": (422, "Запрос не прошёл валидацию: подробности в массиве `errors`."),
}


def _error_table() -> str:
    rows = ["| HTTP | `code` | Когда приходит |", "| --- | --- | --- |"]
    for code, (status, description) in sorted(ERROR_CODES.items(), key=lambda item: (item[1][0], item[0])):
        rows.append(f"| {status} | `{code}` | {description} |")
    return "\n".join(rows)


API_DESCRIPTION = (
    "Бэкенд приложения для пар: регистрация, пары один-к-одному, приглашения и общий календарь, "
    "который работает поверх Google Calendar.\n"
    "\n"
    "## Что нужно знать перед началом\n"
    "\n"
    "- **База URL.** Все эндпоинты живут под `/api/v1`. Пути ниже указаны относительно корня, "
    "итоговый адрес — `<хост>/api/v1/...`.\n"
    "- **Формат.** Только JSON, тело запроса отправляйте с `Content-Type: application/json`.\n"
    "- **Даты и время.** ISO 8601: даты как `YYYY-MM-DD`, моменты времени — с таймзоной "
    "(`2026-10-14T19:00:00+03:00`) или с `Z`.\n"
    "- **Пустые ответы.** Эндпоинты с кодом `204` тела не возвращают вообще, не пытайтесь его распарсить.\n"
    "- **Идентификаторы.** Везде UUID. У событий идентификатор выдаёт Google, см. раздел про события.\n"
    "\n"
    "## Авторизация\n"
    "\n"
    "Все эндпоинты, кроме `/auth/*` и `/health`, требуют заголовок:\n"
    "\n"
    "```\n"
    "Authorization: Bearer <access_token>\n"
    "```\n"
    "\n"
    "Токены выдаются парой: `access_token` и `refresh_token`. Access-токен живёт 30 минут, "
    "refresh-токен — 30 дней. Точный срок access-токена возвращается в поле `expires_in` "
    "(в секундах) вместе с парой токенов.\n"
    "\n"
    "Когда access-токен истёк, сервер отвечает `401` с кодом `invalid_token`. Фронт должен вызвать "
    "`POST /auth/refresh` с `refresh_token`, получить новую пару и повторить исходный запрос. "
    "Если истёк и refresh-токен, сервер тоже вернёт `401` с кодом `invalid_token` — отправляйте "
    "пользователя на экран входа.\n"
    "\n"
    "Выхода из системы на бэкенде нет: logout — это удаление токенов на клиенте. Отозвать уже "
    "выданный токен нельзя, он действует до истечения срока.\n"
    "\n"
    "## Формат ошибок\n"
    "\n"
    "Любая ошибка возвращается в едином виде:\n"
    "\n"
    "```json\n"
    '{"detail": "Invalid or expired token", "code": "invalid_token"}\n'
    "```\n"
    "\n"
    "- `code` — то, на что нужно ветвить логику на фронте.\n"
    "- `detail` — техническое пояснение на английском для отладки. Показывать пользователю не нужно, "
    "лучше показывать свой текст по `code`.\n"
    "\n"
    "Ошибки валидации выглядят иначе: помимо `detail` и `code` там есть массив `errors` с путём до "
    "проблемного поля.\n"
    "\n"
    "```json\n"
    '{"detail": "Validation error", "code": "validation_error", '
    '"errors": [{"loc": ["body", "email"], "msg": "value is not a valid email address", "type": "value_error"}]}\n'
    "```\n"
    "\n"
    "### Полный список кодов ошибок\n"
    "\n"
    + _error_table()
    + "\n"
    "\n"
    "## Сценарий: регистрация и создание пары\n"
    "\n"
    "1. `POST /auth/register` (или `POST /auth/google`) — получить пару токенов.\n"
    "2. `POST /couples` — создать пару. Создатель сразу становится её участником, поэтому "
    "человек может быть только в одной паре.\n"
    "3. `PATCH /couples/me` — заполнить `together_since` и таймзону пары, чтобы фронт мог "
    "показывать «вместе уже N дней» через поле `days_together`.\n"
    "4. `GET /couples/me` — текущее состояние пары: участники, `days_together`, привязанный календарь.\n"
    "\n"
    "## Сценарий: приглашение партнёра\n"
    "\n"
    "1. Один партнёр создаёт пару (`POST /couples`), если она ещё не создана.\n"
    "2. `POST /invitations` — получить код вида `K9HAUV74` и срок жизни. Код действует 7 дней. "
    "Активное приглашение в паре всегда одно: создание нового отменяет предыдущее.\n"
    "3. Второй партнёр регистрируется и смотрит, кто приглашает и в какую пару: `GET /invitations/{code}`.\n"
    "4. `POST /invitations/{code}/accept` — вступить в пару. В ответ приходит пара с двумя участниками.\n"
    "5. Если передумал, создатель приглашения может отменить его: `DELETE /invitations/{code}`.\n"
    "\n"
    "`GET /invitations/me` возвращает активное приглашение текущей пары или `null`, если его нет, — "
    "удобно для экрана «ждём партнёра».\n"
    "\n"
    "## Сценарий: подключение Google Calendar\n"
    "\n"
    "Календарь подключает **один** партнёр — тот, чей Google-календарь станет общим. Второму партнёру "
    "Google подключать не нужно: бэкенд всегда читает и пишет календарь токеном владельца, поэтому "
    "права на события у обоих партнёров всё равно равные.\n"
    "\n"
    "1. `GET /google/connect` — бэкенд вернёт `authorization_url`, подписанный под конкретного пользователя.\n"
    "2. Фронт открывает этот URL, и пользователь даёт согласие в Google.\n"
    "3. Google редиректит на бэкенд, бэкенд обменивает код на токены и **редиректит пользователя на "
    "`FRONTEND_REDIRECT_URL`** с параметром `google=connected` или `google=error`.\n"
    "4. Поймав этот возврат, фронт проверяет состояние: `GET /google/connection` -> `{\"connected\": true}`.\n"
    "5. `GET /google/calendars` — список календарей аккаунта, доступных на запись. Показать выбор.\n"
    "6. `PUT /couple/calendar` с выбранным `calendar_id` — привязать календарь к паре.\n"
    "\n"
    "Важные детали:\n"
    "\n"
    "- Ссылку из `/google/connect` нужно открывать в **системном браузере**. Google запрещает "
    "проводить согласие внутри iframe и такие запросы отклоняет.\n"
    "- Эндпоинт `/google/callback` в этой документации не показан: его вызывает только Google, "
    "фронт его не использует.\n"
    "- Заранее подобранный календарь можно не держать в состоянии: `GET /couples/me` возвращает "
    "поле `calendar`, а `GET /couple/calendar` — привязку напрямую.\n"
    "- Календарь с правами только на чтение отклонится с кодом `calendar_not_writable`.\n"
    "- События читаются и пишутся в момент запроса, фоновой синхронизации нет. Если партнёр "
    "что-то поменял прямо в Google Calendar, это будет видно при следующем `GET /couple/calendar/events`.\n"
    "\n"
    "## События календаря\n"
    "\n"
    "- События **не хранятся** в нашей базе. Источник правды — Google Calendar, `event_id` в ответах "
    "это идентификатор события в Google. Отдельной таблицы событий нет, поэтому `event_id` сразу "
    "передавайте в `GET`/`PATCH`/`DELETE`.\n"
    "- В `start` и `end` нужно передать ровно одно из двух: `date` (целый день) или `date_time` "
    "(конкретное время). Если передать оба или ни одного — `422`.\n"
    "- **Событие на весь день.** `end` в Google исключающий: чтобы сделать событие на один день, "
    "передайте `start.date = \"2026-06-01\"`, `end.date = \"2026-06-02\"`.\n"
    "- **Таймзона.** Если `date_time` без смещения, время трактуется в таймзоне из `time_zone`, "
    "а если её нет — в таймзоне пары. Неизвестная таймзона приводит к фолбэку на UTC.\n"
    "- **Окно выборки.** `GET /couple/calendar/events` без параметров вернёт события от текущего "
    "момента до +30 дней. В `time_min` и `time_max` передавайте ISO 8601 со смещением через `Z` "
    "либо кодируйте `+` как `%2B` — в query-строке сырой `+00:00` превратится в пробел и запрос упадёт с `422`.\n"
    "- **Серии событий.** Повторяющиеся события возвращаются развёрнутыми (`singleEvents`), то есть "
    "по объекту на каждое вхождение, отсортированными по началу. У вхождения свой `id` и поле "
    "`recurring_event_id` со ссылкой на базовое событие. Правки из приложения применяются только к "
    "этому вхождению, редактировать всю серию целиком нельзя.\n"
    "- **Лимит выдачи.** За один запрос возвращается максимум 5000 событий, пагинации нет — сужайте окно.\n"
    "\n"
    "## Ограничения\n"
    "\n"
    "- Пара строго один-к-одному: человек состоит максимум в одной паре.\n"
    "- У обоих партнёров полные равные права, ролей нет.\n"
    "- `PATCH` не умеет очищать необязательные поля события: `description` и `location` можно "
    "только заменить.\n"
    "- Кэша событий нет: `GET /couple/calendar/events` каждый раз обращается к Google, поэтому "
    "ответ зависит от доступности Google API.\n"
    "- Rate-limit на бэкенде не настроен.\n"
)

TAGS_METADATA = [
    {
        "name": "auth",
        "description": (
            "Регистрация, вход по email и через Google, обновление токенов. "
            "Здесь же выдаётся пара `access_token` + `refresh_token`, которая нужна всем "
            "остальным эндпоинтам."
        ),
    },
    {
        "name": "users",
        "description": "Профиль текущего пользователя: чтение и правка имени и аватара.",
    },
    {
        "name": "couples",
        "description": (
            "Пара один-к-одному: создание, состояние, настройки и выход. "
            "Из `GET /couples/me` фронт берёт участников, `together_since`, `days_together` "
            "и привязанный календарь."
        ),
    },
    {
        "name": "invitations",
        "description": (
            "Приглашение партнёра по коду. Код действует 7 дней, активное приглашение в паре "
            "всегда одно."
        ),
    },
    {
        "name": "google",
        "description": (
            "Подключение Google-аккаунта и выбор календаря. Полный пошаговый сценарий описан "
            "в разделе «Сценарий: подключение Google Calendar» в общем описании API."
        ),
    },
    {
        "name": "calendar",
        "description": (
            "Привязка общего календаря пары и работа с событиями. События не хранятся у нас: "
            "запросы проксируются в Google Calendar."
        ),
    },
    {
        "name": "service",
        "description": "Служебные эндпоинты для мониторинга.",
    },
]

UNAUTHORIZED_DESCRIPTION = (
    "Нужен действующий access-токен в заголовке `Authorization: Bearer <access_token>`. "
    "Коды: `missing_token`, `invalid_token`."
)

VALIDATION_DESCRIPTION = (
    "Запрос не прошёл валидацию: неверный тип, отсутствующее обязательное поле, "
    "нарушены ограничения полей."
)

ERROR_REF = "#/components/schemas/ErrorResponse"
VALIDATION_REF = "#/components/schemas/ValidationErrorResponse"

UNAUTHORIZED_RESPONSE = {
    "description": UNAUTHORIZED_DESCRIPTION,
    "content": {"application/json": {"schema": {"$ref": ERROR_REF}}},
}

VALIDATION_RESPONSE = {
    "description": VALIDATION_DESCRIPTION,
    "content": {"application/json": {"schema": {"$ref": VALIDATION_REF}}},
}


def error_response(description: str) -> dict:
    return {
        "description": description,
        "content": {"application/json": {"schema": {"$ref": ERROR_REF}}},
    }


def _collect_refs(node: object) -> set[str]:
    refs: set[str] = set()
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "$ref" and isinstance(value, str):
                refs.add(value)
            else:
                refs.update(_collect_refs(value))
    elif isinstance(node, list):
        for item in node:
            refs.update(_collect_refs(item))
    return refs


def _inject_shared_responses(schema: dict) -> None:
    for path_item in schema.get("paths", {}).values():
        for operation in path_item.values():
            if not isinstance(operation, dict):
                continue
            responses = operation.setdefault("responses", {})
            if operation.get("security") and "401" not in responses:
                responses["401"] = deepcopy(UNAUTHORIZED_RESPONSE)
            if "422" in responses:
                responses["422"] = deepcopy(VALIDATION_RESPONSE)


def _register_error_schemas(schema: dict) -> None:
    _, definitions = models_json_schema(
        [(ErrorResponse, "validation"), (ValidationErrorResponse, "validation")],
        ref_template="#/components/schemas/{model}",
    )
    schema["components"].setdefault("schemas", {}).update(definitions["$defs"])


def _tidy_components(schema: dict) -> None:
    components = schema.get("components", {})
    schemas = components.get("schemas", {})
    used_refs = _collect_refs(schema.get("paths", {}))
    for name in ("HTTPValidationError", "ValidationError"):
        if name in schemas and f"#/components/schemas/{name}" not in used_refs:
            del schemas[name]
    if "ErrorResponse" in schemas:
        schemas["ErrorResponse"]["x-error-codes"] = sorted(ERROR_CODES)


def install_openapi(app: FastAPI) -> None:
    original_openapi = app.openapi

    def custom_openapi() -> dict:
        if app.openapi_schema:
            return app.openapi_schema
        schema = original_openapi()
        _register_error_schemas(schema)
        _inject_shared_responses(schema)
        _tidy_components(schema)
        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi
