from urllib.parse import urlencode

import httpx

from app.core.config import get_settings
from app.core.errors import BadRequest, ConfigurationError, GoogleApiError

GOOGLE_AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GOOGLE_REVOKE_ENDPOINT = "https://oauth2.googleapis.com/revoke"
GOOGLE_TOKEN_INFO_ENDPOINT = "https://oauth2.googleapis.com/tokeninfo"

CALENDAR_SCOPES = (
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.calendars.readonly",
)


def build_authorization_url(state: str) -> str:
    settings = get_settings()
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_oauth_redirect_uri,
        "response_type": "code",
        "scope": " ".join(CALENDAR_SCOPES),
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
        "state": state,
    }
    return f"{GOOGLE_AUTHORIZATION_ENDPOINT}?{urlencode(params)}"


async def exchange_code(code: str) -> dict:
    settings = get_settings()
    data = {
        "code": code,
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "redirect_uri": settings.google_oauth_redirect_uri,
        "grant_type": "authorization_code",
    }
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(GOOGLE_TOKEN_ENDPOINT, data=data)
    if response.status_code != 200:
        raise GoogleApiError(f"Google rejected the authorization code: {response.text}")
    return response.json()


async def refresh_access_token(refresh_token: str) -> dict:
    settings = get_settings()
    data = {
        "refresh_token": refresh_token,
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "grant_type": "refresh_token",
    }
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(GOOGLE_TOKEN_ENDPOINT, data=data)
    if response.status_code != 200:
        raise GoogleApiError(f"Google rejected the refresh token: {response.text}")
    return response.json()


async def revoke_token(token: str) -> None:
    async with httpx.AsyncClient(timeout=15) as client:
        await client.post(GOOGLE_REVOKE_ENDPOINT, data={"token": token})


async def verify_id_token(id_token: str) -> dict:
    settings = get_settings()
    if not settings.google_client_id:
        raise ConfigurationError(
            "Google login is not configured: GOOGLE_CLIENT_ID is missing",
            code="google_login_not_configured",
        )
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(GOOGLE_TOKEN_INFO_ENDPOINT, params={"id_token": id_token})
    if response.status_code != 200:
        raise BadRequest("Google id_token is invalid or expired", code="invalid_google_token")
    claims = response.json()
    if claims.get("aud") != settings.google_client_id:
        raise BadRequest("Google id_token audience mismatch", code="invalid_google_token")
    if claims.get("email_verified") not in (True, "true"):
        raise BadRequest("Google account email is not verified", code="google_email_not_verified")
    if not claims.get("sub") or not claims.get("email"):
        raise BadRequest("Google id_token has no subject or email", code="invalid_google_token")
    return claims
