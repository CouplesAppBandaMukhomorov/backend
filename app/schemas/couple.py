import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator

from app.schemas.calendar import CalendarLink
from app.schemas.user import UserShort


class CoupleCreate(BaseModel):
    title: str | None = Field(default=None, max_length=120)
    timezone: str = Field(default="UTC", max_length=64)
    together_since: date | None = None


class CoupleUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=120)
    timezone: str | None = Field(default=None, max_length=64)
    together_since: date | None = None

    @model_validator(mode="after")
    def reject_null_timezone(self) -> "CoupleUpdate":
        if self.timezone is None and "timezone" in self.model_fields_set:
            raise ValueError("'timezone' cannot be null")
        return self


class CoupleRead(BaseModel):
    id: uuid.UUID
    title: str | None
    timezone: str
    together_since: date | None
    days_together: int | None
    created_at: datetime
    members: list[UserShort]
    calendar: CalendarLink | None
