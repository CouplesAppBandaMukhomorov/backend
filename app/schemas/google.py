from datetime import datetime

from pydantic import BaseModel


class GoogleAuthorizeUrl(BaseModel):
    authorization_url: str


class GoogleConnectionRead(BaseModel):
    connected: bool
    scope: str | None = None
    expires_at: datetime | None = None


class GoogleCalendarRead(BaseModel):
    id: str
    summary: str
    description: str | None = None
    timezone: str | None = None
    access_role: str | None = None
    primary: bool = False
