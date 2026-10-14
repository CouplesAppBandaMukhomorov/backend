from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.openapi import API_DESCRIPTION, TAGS_METADATA, install_openapi
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import ApiError
from app.db.session import engine

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    await engine.dispose()


app_options: dict = {
    "title": settings.app_name,
    "version": settings.app_version,
    "description": API_DESCRIPTION,
    "openapi_tags": TAGS_METADATA,
    "lifespan": lifespan,
}
if settings.api_server_url:
    app_options["servers"] = [{"url": settings.api_server_url}]

app = FastAPI(**app_options)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ApiError)
async def api_error_handler(_request: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message, "code": exc.code},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = [
        {"loc": list(error.get("loc", [])), "msg": error.get("msg"), "type": error.get("type")}
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content=jsonable_encoder(
            {"detail": "Validation error", "code": "validation_error", "errors": errors}
        ),
    )


@app.get(
    "/health",
    tags=["service"],
    summary="Проверка живости сервиса",
    description="Возвращает `{\"status\": \"ok\"}`, если процесс поднят. "
    "Базу данных и Google не проверяет, для мониторинга хватает этого ответа.",
)
async def health() -> dict:
    return {"status": "ok"}


app.include_router(api_router, prefix=settings.api_v1_prefix)

install_openapi(app)
