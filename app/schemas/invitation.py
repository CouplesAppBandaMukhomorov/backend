import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.couple import CoupleRead
from app.schemas.user import UserShort


class InvitationRead(BaseModel):
    id: uuid.UUID
    couple_id: uuid.UUID
    code: str
    status: str
    expires_at: datetime
    created_at: datetime
    inviter: UserShort
    invited_user: UserShort | None = None


class InvitationPreview(BaseModel):
    code: str
    status: str
    couple_id: uuid.UUID
    couple_title: str | None
    expires_at: datetime
    inviter: UserShort


class InvitationAcceptResponse(BaseModel):
    couple: CoupleRead
