from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_couple, get_current_user
from app.db.session import get_db
from app.models.couple import Couple
from app.models.user import User
from app.schemas.couple import CoupleCreate, CoupleRead, CoupleUpdate
from app.services import couple_service

router = APIRouter(prefix="/couples", tags=["couples"])


@router.post("", response_model=CoupleRead, status_code=status.HTTP_201_CREATED)
async def create_couple(
    payload: CoupleCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CoupleRead:
    return await couple_service.create_couple(db, user, payload)


@router.get("/me", response_model=CoupleRead)
async def read_couple(couple: Couple = Depends(get_current_couple)) -> CoupleRead:
    return couple_service.to_couple_read(couple)


@router.patch("/me", response_model=CoupleRead)
async def update_couple(
    payload: CoupleUpdate,
    couple: Couple = Depends(get_current_couple),
    db: AsyncSession = Depends(get_db),
) -> CoupleRead:
    return await couple_service.update_couple(db, couple, payload)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def leave_couple(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await couple_service.leave_couple(db, user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
