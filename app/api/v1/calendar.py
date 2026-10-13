from datetime import datetime

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_couple, get_current_user
from app.db.session import get_db
from app.models.couple import Couple
from app.models.user import User
from app.schemas.calendar import (
    CalendarLink,
    CalendarLinkRequest,
    EventCreate,
    EventRead,
    EventUpdate,
)
from app.services import calendar_service

router = APIRouter(prefix="/couple/calendar", tags=["calendar"])


@router.get("", response_model=CalendarLink | None)
async def read_link(couple: Couple = Depends(get_current_couple)) -> CalendarLink | None:
    return calendar_service.get_link(couple)


@router.put("", response_model=CalendarLink)
async def link_calendar(
    payload: CalendarLinkRequest,
    couple: Couple = Depends(get_current_couple),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CalendarLink:
    return await calendar_service.link_calendar(db, couple, user, payload.calendar_id)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def unlink_calendar(
    couple: Couple = Depends(get_current_couple),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await calendar_service.unlink_calendar(db, couple)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/events", response_model=list[EventRead])
async def list_events(
    time_min: datetime | None = None,
    time_max: datetime | None = None,
    couple: Couple = Depends(get_current_couple),
    db: AsyncSession = Depends(get_db),
) -> list[EventRead]:
    return await calendar_service.list_events(db, couple, time_min, time_max)


@router.post("/events", response_model=EventRead, status_code=status.HTTP_201_CREATED)
async def create_event(
    payload: EventCreate,
    couple: Couple = Depends(get_current_couple),
    db: AsyncSession = Depends(get_db),
) -> EventRead:
    return await calendar_service.create_event(db, couple, payload)


@router.get("/events/{event_id}", response_model=EventRead)
async def read_event(
    event_id: str,
    couple: Couple = Depends(get_current_couple),
    db: AsyncSession = Depends(get_db),
) -> EventRead:
    return await calendar_service.get_event(db, couple, event_id)


@router.patch("/events/{event_id}", response_model=EventRead)
async def update_event(
    event_id: str,
    payload: EventUpdate,
    couple: Couple = Depends(get_current_couple),
    db: AsyncSession = Depends(get_db),
) -> EventRead:
    return await calendar_service.update_event(db, couple, event_id, payload)


@router.delete("/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    event_id: str,
    couple: Couple = Depends(get_current_couple),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await calendar_service.delete_event(db, couple, event_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
