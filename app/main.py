from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import ApiError
from app.db.session import engine

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

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


@app.get("/health", tags=["service"])
async def health() -> dict:
    return {"status": "ok"}


app.include_router(api_router, prefix=settings.api_v1_prefix)
