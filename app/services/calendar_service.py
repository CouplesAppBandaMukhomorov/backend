from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequest, CalendarNotLinked
from app.integrations.google.calendar import GoogleCalendarClient
from app.models.couple import Couple
from app.models.user import User
from app.schemas.calendar import (
    CalendarLink,
    EventCreate,
    EventDateTime,
    EventRead,
    EventUpdate,
)
from app.services import google_service

DEFAULT_EVENT_WINDOW_DAYS = 30


def get_link(couple: Couple) -> CalendarLink | None:
    if not couple.calendar_id or not couple.calendar_owner_id:
        return None
    return CalendarLink(
        calendar_id=couple.calendar_id,
        summary=couple.calendar_summary,
        owner_id=couple.calendar_owner_id,
    )


async def link_calendar(db: AsyncSession, couple: Couple, user: User, calendar_id: str) -> CalendarLink:
    access_token = await google_service.get_access_token(db, user.id)
    async with GoogleCalendarClient(access_token) as client:
        calendars = await client.list_calendars()

    match = next((item for item in calendars if item.get("id") == calendar_id), None)
    if match is None:
        raise BadRequest(
            "This calendar is not writable by the connected Google account",
            code="calendar_not_available",
        )
    if match.get("accessRole") not in ("owner", "writer"):
        raise BadRequest(
            "This calendar is read-only for the connected Google account",
            code="calendar_not_writable",
        )

    couple.calendar_id = calendar_id
    couple.calendar_summary = match.get("summary")
    couple.calendar_owner_id = user.id
    await db.commit()
    await db.refresh(couple)
    return CalendarLink(
        calendar_id=calendar_id,
        summary=couple.calendar_summary,
        owner_id=user.id,
    )


async def unlink_calendar(db: AsyncSession, couple: Couple) -> None:
    couple.calendar_id = None
    couple.calendar_summary = None
    couple.calendar_owner_id = None
    await db.commit()


async def _context(db: AsyncSession, couple: Couple) -> tuple[str, str]:
    if not couple.calendar_id or not couple.calendar_owner_id:
        raise CalendarNotLinked(
            "No Google calendar is linked to this couple",
            code="calendar_not_linked",
        )
    access_token = await google_service.get_access_token(db, couple.calendar_owner_id)
    return couple.calendar_id, access_token


async def list_events(
    db: AsyncSession,
    couple: Couple,
    time_min: datetime | None,
    time_max: datetime | None,
) -> list[EventRead]:
    calendar_id, access_token = await _context(db, couple)

    start = _ensure_aware(time_min) if time_min else datetime.now(timezone.utc)
    end = _ensure_aware(time_max) if time_max else start + timedelta(days=DEFAULT_EVENT_WINDOW_DAYS)
    if end <= start:
        raise BadRequest("'time_max' must be greater than 'time_min'", code="invalid_time_range")

    async with GoogleCalendarClient(access_token) as client:
        raw_events = await client.list_events(calendar_id, start.isoformat(), end.isoformat())

    return [to_event_read(item) for item in raw_events if item.get("status") != "cancelled"]


async def get_event(db: AsyncSession, couple: Couple, event_id: str) -> EventRead:
    calendar_id, access_token = await _context(db, couple)
    async with GoogleCalendarClient(access_token) as client:
        raw = await client.get_event(calendar_id, event_id)
    return to_event_read(raw)


async def create_event(db: AsyncSession, couple: Couple, payload: EventCreate) -> EventRead:
    calendar_id, access_token = await _context(db, couple)
    body = _build_payload(payload, couple.timezone)
    async with GoogleCalendarClient(access_token) as client:
        raw = await client.create_event(calendar_id, body)
    return to_event_read(raw)


async def update_event(
    db: AsyncSession,
    couple: Couple,
    event_id: str,
    payload: EventUpdate,
) -> EventRead:
    calendar_id, access_token = await _context(db, couple)
    body = _build_payload(payload, couple.timezone)
    if not body:
        raise BadRequest("Nothing to update", code="empty_update")
    async with GoogleCalendarClient(access_token) as client:
        raw = await client.update_event(calendar_id, event_id, body)
    return to_event_read(raw)


async def delete_event(db: AsyncSession, couple: Couple, event_id: str) -> None:
    calendar_id, access_token = await _context(db, couple)
    async with GoogleCalendarClient(access_token) as client:
        await client.delete_event(calendar_id, event_id)


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _build_time(value: EventDateTime, default_timezone: str) -> dict:
    if value.date is not None:
        return {"date": value.date.isoformat()}
    if value.date_time is None:
        raise BadRequest("Event time is missing", code="invalid_event_time")

    moment = value.date_time
    timezone_name = value.time_zone or default_timezone or "UTC"
    if moment.tzinfo is None:
        try:
            moment = moment.replace(tzinfo=ZoneInfo(timezone_name))
        except (ZoneInfoNotFoundError, ValueError):
            moment = moment.replace(tzinfo=timezone.utc)
            timezone_name = "UTC"
    return {"dateTime": moment.isoformat(), "timeZone": timezone_name}


def _build_payload(payload: EventCreate | EventUpdate, default_timezone: str) -> dict:
    body: dict = {}
    for field in ("summary", "description", "location"):
        value = getattr(payload, field)
        if value is not None:
            body[field] = value
    if payload.color_id is not None:
        body["colorId"] = payload.color_id
    if payload.attendees is not None:
        body["attendees"] = [{"email": email} for email in payload.attendees]
    if payload.reminders is not None:
        reminders: dict = {}
        if payload.reminders.use_default is not None:
            reminders["useDefault"] = payload.reminders.use_default
        if payload.reminders.overrides is not None:
            reminders["overrides"] = payload.reminders.overrides
        body["reminders"] = reminders
    if payload.start is not None:
        body["start"] = _build_time(payload.start, default_timezone)
    if payload.end is not None:
        body["end"] = _build_time(payload.end, default_timezone)
    return body


def to_event_read(raw: dict) -> EventRead:
    start = raw.get("start") or {}
    end = raw.get("end") or {}
    attendees = raw.get("attendees") or []
    updated = raw.get("updated")
    return EventRead(
        id=raw["id"],
        summary=raw.get("summary"),
        description=raw.get("description"),
        location=raw.get("location"),
        start=EventDateTime(
            date=start.get("date"),
            date_time=start.get("dateTime"),
            time_zone=start.get("timeZone"),
        ),
        end=EventDateTime(
            date=end.get("date"),
            date_time=end.get("dateTime"),
            time_zone=end.get("timeZone"),
        ),
        is_all_day=bool(start.get("date")),
        status=raw.get("status"),
        html_link=raw.get("htmlLink"),
        recurring_event_id=raw.get("recurringEventId"),
        attendees=[item.get("email") for item in attendees] or None,
        updated=datetime.fromisoformat(updated.replace("Z", "+00:00")) if updated else None,
    )
