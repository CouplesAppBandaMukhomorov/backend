class ApiError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        status_code: int | None = None,
    ) -> None:
        self.message = message or self.__class__.__name__
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
        super().__init__(self.message)


class BadRequest(ApiError):
    status_code = 400
    code = "bad_request"


class Unauthorized(ApiError):
    status_code = 401
    code = "unauthorized"


class Forbidden(ApiError):
    status_code = 403
    code = "forbidden"


class NotFound(ApiError):
    status_code = 404
    code = "not_found"


class Conflict(ApiError):
    status_code = 409
    code = "conflict"


class ConfigurationError(ApiError):
    status_code = 500
    code = "server_misconfigured"


class GoogleApiError(ApiError):
    status_code = 502
    code = "google_api_error"


class GoogleNotConnected(GoogleApiError):
    status_code = 409
    code = "google_not_connected"


class CalendarNotLinked(GoogleApiError):
    status_code = 409
    code = "calendar_not_linked"
