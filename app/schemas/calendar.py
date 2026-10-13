import uuid
from datetime import date as DateType
from datetime import datetime as DateTimeType

from pydantic import BaseModel, Field, model_validator


class CalendarLinkRequest(BaseModel):
    calendar_id: str = Field(min_length=1, max_length=255)


class CalendarLink(BaseModel):
    calendar_id: str
    summary: str | None
    owner_id: uuid.UUID


class EventDateTime(BaseModel):
    date: DateType | None = None
    date_time: DateTimeType | None = None
    time_zone: str | None = None


class EventReminders(BaseModel):
    use_default: bool | None = None
    overrides: list[dict] | None = None


class EventBase(BaseModel):
    summary: str | None = Field(default=None, max_length=1024)
    description: str | None = None
    location: str | None = None
    start: EventDateTime | None = None
    end: EventDateTime | None = None
    reminders: EventReminders | None = None
    attendees: list[str] | None = None
    color_id: str | None = None


class EventCreate(EventBase):
    summary: str = Field(min_length=1, max_length=1024)
    start: EventDateTime
    end: EventDateTime

    @model_validator(mode="after")
    def validate_times(self) -> "EventCreate":
        for name in ("start", "end"):
            value = getattr(self, name)
            if (value.date is None) == (value.date_time is None):
                raise ValueError(f"'{name}' must define exactly one of 'date' or 'date_time'")
        return self


class EventUpdate(EventBase):
    @model_validator(mode="after")
    def validate_times(self) -> "EventUpdate":
        for name in ("start", "end"):
            value = getattr(self, name)
            if value is None:
                continue
            if (value.date is None) == (value.date_time is None):
                raise ValueError(f"'{name}' must define exactly one of 'date' or 'date_time'")
        return self


class EventRead(BaseModel):
    id: str
    summary: str | None
    description: str | None
    location: str | None
    start: EventDateTime
    end: EventDateTime
    is_all_day: bool
    status: str | None = None
    html_link: str | None = None
    recurring_event_id: str | None = None
    attendees: list[str] | None = None
    updated: DateTimeType | None = None
