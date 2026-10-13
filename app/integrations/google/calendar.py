import httpx

from app.core.config import get_settings
from app.core.errors import GoogleApiError

MAX_PAGES = 20


class GoogleCalendarClient:
    def __init__(self, access_token: str) -> None:
        self._client = httpx.AsyncClient(
            base_url=get_settings().google_calendar_api_base,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=20,
        )

    async def __aenter__(self) -> "GoogleCalendarClient":
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self._client.aclose()

    async def _request(self, method: str, url: str, **kwargs: object) -> dict:
        response = await self._client.request(method, url, **kwargs)
        if response.status_code == 204:
            return {}
        if response.status_code >= 400:
            raise self._build_error(response)
        return response.json()

    @staticmethod
    def _build_error(response: httpx.Response) -> GoogleApiError:
        try:
            payload = response.json()
            message = payload.get("error", {}).get("message") or response.text
        except ValueError:
            message = response.text
        if response.status_code == 404:
            return GoogleApiError(message, code="calendar_not_found", status_code=404)
        if response.status_code in (401, 403):
            return GoogleApiError(message, code="google_access_denied", status_code=403)
        return GoogleApiError(message)

    async def list_calendars(self) -> list[dict]:
        data = await self._request(
            "GET",
            "/users/me/calendarList",
            params={"minAccessRole": "writer", "maxResults": 250},
        )
        return data.get("items", [])

    async def get_calendar(self, calendar_id: str) -> dict:
        return await self._request("GET", f"/calendars/{calendar_id}")

    async def list_events(self, calendar_id: str, time_min: str, time_max: str) -> list[dict]:
        events: list[dict] = []
        page_token: str | None = None
        for _ in range(MAX_PAGES):
            params: dict[str, str] = {
                "timeMin": time_min,
                "timeMax": time_max,
                "singleEvents": "true",
                "orderBy": "startTime",
                "maxResults": "250",
            }
            if page_token:
                params["pageToken"] = page_token
            data = await self._request("GET", f"/calendars/{calendar_id}/events", params=params)
            events.extend(data.get("items", []))
            page_token = data.get("nextPageToken")
            if not page_token:
                break
        return events

    async def get_event(self, calendar_id: str, event_id: str) -> dict:
        return await self._request("GET", f"/calendars/{calendar_id}/events/{event_id}")

    async def create_event(self, calendar_id: str, payload: dict) -> dict:
        return await self._request("POST", f"/calendars/{calendar_id}/events", json=payload)

    async def update_event(self, calendar_id: str, event_id: str, payload: dict) -> dict:
        return await self._request("PATCH", f"/calendars/{calendar_id}/events/{event_id}", json=payload)

    async def delete_event(self, calendar_id: str, event_id: str) -> None:
        await self._request("DELETE", f"/calendars/{calendar_id}/events/{event_id}")
