from fastapi import APIRouter

from app.api.v1 import auth, calendar, couples, google_auth, invitations, notes, users

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(couples.router)
api_router.include_router(invitations.router)
api_router.include_router(google_auth.router)
api_router.include_router(calendar.router)
api_router.include_router(notes.router)
