import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    display_name: str
    avatar_url: str | None
    created_at: datetime


class UserShort(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    display_name: str
    avatar_url: str | None


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    avatar_url: str | None = Field(default=None, max_length=1024)

    @model_validator(mode="after")
    def reject_null_display_name(self) -> "UserUpdate":
        if self.display_name is None and "display_name" in self.model_fields_set:
            raise ValueError("'display_name' cannot be null")
        return self
