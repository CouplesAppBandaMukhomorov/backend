from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

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


@router.post("/register", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)) -> TokenPair:
    return await auth_service.register(db, payload)


@router.post("/login", response_model=TokenPair)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenPair:
    return await auth_service.login(db, payload)


@router.post("/google", response_model=TokenPair)
async def login_with_google(
    payload: GoogleLoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenPair:
    return await auth_service.login_with_google(db, payload.id_token)


@router.post("/refresh", response_model=TokenPair)
async def refresh(payload: RefreshRequest, db: AsyncSession = Depends(get_db)) -> TokenPair:
    return await auth_service.refresh(db, payload.refresh_token)
