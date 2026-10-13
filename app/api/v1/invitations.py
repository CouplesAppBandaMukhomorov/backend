from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.invitation import (
    InvitationAcceptResponse,
    InvitationPreview,
    InvitationRead,
)
from app.services import invitation_service

router = APIRouter(prefix="/invitations", tags=["invitations"])


@router.post("", response_model=InvitationRead, status_code=status.HTTP_201_CREATED)
async def create_invitation(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvitationRead:
    return await invitation_service.create_invitation(db, user)


@router.get("/me", response_model=InvitationRead | None)
async def read_active_invitation(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvitationRead | None:
    return await invitation_service.get_active_invitation(db, user)


@router.get("/{code}", response_model=InvitationPreview)
async def read_invitation(
    code: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvitationPreview:
    return await invitation_service.get_preview(db, code)


@router.post("/{code}/accept", response_model=InvitationAcceptResponse)
async def accept_invitation(
    code: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvitationAcceptResponse:
    return await invitation_service.accept_invitation(db, user, code)


@router.delete("/{code}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_invitation(
    code: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await invitation_service.cancel_invitation(db, user, code)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
