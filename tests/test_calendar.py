import json

import httpx
import pytest
import respx

CALENDAR_LIST_URL = "https://www.googleapis.com/calendar/v3/users/me/calendarList"
EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/cal-1/events"
CALENDAR_ID = "cal-1"


def calendar_list_response() -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "items": [
                {
                    "id": CALENDAR_ID,
                    "summary": "Our calendar",
                    "timeZone": "Europe/Moscow",
                    "accessRole": "owner",
                    "primary": True,
                }
            ]
        },
    )


def event_payload(event_id: str = "evt-1", summary: str = "Dinner") -> dict:
    return {
        "id": event_id,
        "status": "confirmed",
        "summary": summary,
        "description": "Italian place",
        "location": "Main street 1",
        "start": {"dateTime": "2026-10-14T19:00:00+03:00", "timeZone": "Europe/Moscow"},
        "end": {"dateTime": "2026-10-14T21:00:00+03:00", "timeZone": "Europe/Moscow"},
        "htmlLink": "https://calendar.google.com/event?eid=evt-1",
        "updated": "2026-10-01T10:00:00.000Z",
    }


@pytest.fixture
def google_api():
    with respx.mock(assert_all_called=False) as router:
        yield router


async def link_calendar(client, make_couple, connect_google, google_api):
    tokens, headers, _ = await make_couple("owner@example.com")
    google_api.get(url__startswith=CALENDAR_LIST_URL).mock(return_value=calendar_list_response())
    google_headers = await connect_google(tokens)

    response = await client.put(
        "/api/v1/couple/calendar",
        json={"calendar_id": CALENDAR_ID},
        headers=google_headers,
    )
    assert response.status_code == 200, response.text
    return headers


async def test_link_and_unlink_calendar(client, make_couple, connect_google, google_api):
    headers = await link_calendar(client, make_couple, connect_google, google_api)

    link = await client.get("/api/v1/couple/calendar", headers=headers)
    assert link.status_code == 200
    assert link.json()["calendar_id"] == CALENDAR_ID

    unlinked = await client.delete("/api/v1/couple/calendar", headers=headers)
    assert unlinked.status_code == 204

    empty = await client.get("/api/v1/couple/calendar", headers=headers)
    assert empty.json() is None


async def test_link_calendar_rejects_unknown_id(client, make_couple, connect_google, google_api):
    tokens, _, _ = await make_couple("owner@example.com")
    google_api.get(url__startswith=CALENDAR_LIST_URL).mock(return_value=calendar_list_response())
    headers = await connect_google(tokens)

    response = await client.put(
        "/api/v1/couple/calendar",
        json={"calendar_id": "someone-elses-calendar"},
        headers=headers,
    )
    assert response.status_code == 400
    assert response.json()["code"] == "calendar_not_available"


async def test_link_calendar_rejects_read_only_calendar(client, make_couple, connect_google, google_api):
    tokens, _, _ = await make_couple("owner@example.com")
    google_api.get(url__startswith=CALENDAR_LIST_URL).mock(
        return_value=httpx.Response(
            200,
            json={"items": [{"id": CALENDAR_ID, "summary": "Holidays", "accessRole": "reader"}]},
        )
    )
    headers = await connect_google(tokens)

    response = await client.put(
        "/api/v1/couple/calendar",
        json={"calendar_id": CALENDAR_ID},
        headers=headers,
    )
    assert response.status_code == 400
    assert response.json()["code"] == "calendar_not_writable"


async def test_calendar_requires_google_connection(client, make_couple):
    _, headers, _ = await make_couple("owner@example.com")

    response = await client.put(
        "/api/v1/couple/calendar",
        json={"calendar_id": CALENDAR_ID},
        headers=headers,
    )
    assert response.status_code == 409
    assert response.json()["code"] == "google_not_connected"


async def test_events_require_linked_calendar(client, make_couple):
    _, headers, _ = await make_couple("owner@example.com")

    response = await client.get("/api/v1/couple/calendar/events", headers=headers)
    assert response.status_code == 409
    assert response.json()["code"] == "calendar_not_linked"


async def test_list_create_update_delete_event(
    client, make_couple, connect_google, google_api
):
    headers = await link_calendar(client, make_couple, connect_google, google_api)

    google_api.get(url__regex=rf"{EVENTS_URL}\?.*").mock(
        return_value=httpx.Response(200, json={"items": [event_payload()]})
    )

    listed = await client.get(
        "/api/v1/couple/calendar/events",
        headers=headers,
        params={"time_min": "2026-10-01T00:00:00+00:00", "time_max": "2026-11-01T00:00:00+00:00"},
    )
    assert listed.status_code == 200, listed.text
    events = listed.json()
    assert len(events) == 1
    assert events[0]["summary"] == "Dinner"
    assert events[0]["is_all_day"] is False
    assert events[0]["attendees"] is None

    google_api.post(url__regex=rf"{EVENTS_URL}$").mock(
        return_value=httpx.Response(200, json=event_payload("evt-new", "Picnic"))
    )
    created = await client.post(
        "/api/v1/couple/calendar/events",
        headers=headers,
        json={
            "summary": "Picnic",
            "start": {"date_time": "2026-10-14T19:00:00+03:00", "time_zone": "Europe/Moscow"},
            "end": {"date_time": "2026-10-14T21:00:00+03:00", "time_zone": "Europe/Moscow"},
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["id"] == "evt-new"
    assert created.json()["summary"] == "Picnic"

    google_api.get(url__regex=rf"{EVENTS_URL}/evt-1$").mock(
        return_value=httpx.Response(200, json=event_payload())
    )
    single = await client.get("/api/v1/couple/calendar/events/evt-1", headers=headers)
    assert single.status_code == 200
    assert single.json()["id"] == "evt-1"

    google_api.patch(url__regex=rf"{EVENTS_URL}/evt-1$").mock(
        return_value=httpx.Response(200, json=event_payload("evt-1", "Dinner updated"))
    )
    updated = await client.patch(
        "/api/v1/couple/calendar/events/evt-1",
        headers=headers,
        json={"summary": "Dinner updated"},
    )
    assert updated.status_code == 200
    assert updated.json()["summary"] == "Dinner updated"

    google_api.delete(url__regex=rf"{EVENTS_URL}/evt-1$").mock(return_value=httpx.Response(204))
    deleted = await client.delete("/api/v1/couple/calendar/events/evt-1", headers=headers)
    assert deleted.status_code == 204


async def test_all_day_event_is_flagged(client, make_couple, connect_google, google_api):
    headers = await link_calendar(client, make_couple, connect_google, google_api)

    google_api.get(url__regex=rf"{EVENTS_URL}\?.*").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": "evt-anniversary",
                        "status": "confirmed",
                        "summary": "Anniversary",
                        "start": {"date": "2026-06-01"},
                        "end": {"date": "2026-06-02"},
                    }
                ]
            },
        )
    )

    response = await client.get("/api/v1/couple/calendar/events", headers=headers)
    assert response.status_code == 200
    event = response.json()[0]
    assert event["is_all_day"] is True
    assert event["start"]["date"] == "2026-06-01"


async def test_create_event_validates_time_shape(client, make_couple, connect_google, google_api):
    headers = await link_calendar(client, make_couple, connect_google, google_api)

    response = await client.post(
        "/api/v1/couple/calendar/events",
        headers=headers,
        json={
            "summary": "Broken",
            "start": {"date": "2026-10-14", "date_time": "2026-10-14T19:00:00+03:00"},
            "end": {"date_time": "2026-10-14T21:00:00+03:00"},
        },
    )
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


async def test_rejects_unknown_time_zone_by_falling_back(client, make_couple, connect_google, google_api):
    headers = await link_calendar(client, make_couple, connect_google, google_api)

    captured: dict = {}

    def capture(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, json=event_payload("evt-tz"))

    google_api.post(url__regex=rf"{EVENTS_URL}$").mock(side_effect=capture)

    response = await client.post(
        "/api/v1/couple/calendar/events",
        headers=headers,
        json={
            "summary": "Timezone check",
            "start": {"date_time": "2026-10-14T19:00:00", "time_zone": "Not/AZone"},
            "end": {"date_time": "2026-10-14T21:00:00", "time_zone": "Not/AZone"},
        },
    )
    assert response.status_code == 201, response.text
    assert captured["start"]["timeZone"] == "UTC"
    assert captured["start"]["dateTime"].endswith("+00:00")


async def test_google_calendars_endpoint_lists_calendars(
    client, make_couple, connect_google, google_api
):
    tokens, _, _ = await make_couple("owner@example.com")
    google_api.get(url__startswith=CALENDAR_LIST_URL).mock(return_value=calendar_list_response())
    headers = await connect_google(tokens)

    response = await client.get("/api/v1/google/calendars", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json() == [
        {
            "id": CALENDAR_ID,
            "summary": "Our calendar",
            "description": None,
            "timezone": "Europe/Moscow",
            "access_role": "owner",
            "primary": True,
        }
    ]


async def test_leaving_owner_unlinks_calendar(client, make_couple, connect_google, google_api, register):
    tokens, owner_headers, _ = await make_couple("owner@example.com")
    google_api.get(url__startswith=CALENDAR_LIST_URL).mock(return_value=calendar_list_response())
    owner_headers = await connect_google(tokens)

    linked = await client.put(
        "/api/v1/couple/calendar",
        json={"calendar_id": CALENDAR_ID},
        headers=owner_headers,
    )
    assert linked.status_code == 200, linked.text

    partner_tokens = await register("partner@example.com")
    partner_headers = {"Authorization": f"Bearer {partner_tokens['access_token']}"}
    invitation = await client.post("/api/v1/invitations", headers=owner_headers)
    await client.post(
        f"/api/v1/invitations/{invitation.json()['code']}/accept",
        headers=partner_headers,
    )

    left = await client.delete("/api/v1/couples/me", headers=owner_headers)
    assert left.status_code == 204

    remaining = await client.get("/api/v1/couple/calendar", headers=partner_headers)
    assert remaining.status_code == 200
    assert remaining.json() is None

    events = await client.get("/api/v1/couple/calendar/events", headers=partner_headers)
    assert events.status_code == 409
    assert events.json()["code"] == "calendar_not_linked"


async def test_connection_status_without_google(client, register, auth_headers):
    tokens = await register("alone@example.com")

    response = await client.get("/api/v1/google/connection", headers=auth_headers(tokens))
    assert response.status_code == 200
    assert response.json()["connected"] is False


async def test_connect_returns_authorization_url(client, register, auth_headers):
    tokens = await register("alone@example.com")

    response = await client.get("/api/v1/google/connect", headers=auth_headers(tokens))
    assert response.status_code == 200
    url = response.json()["authorization_url"]
    assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert "calendar.events" in url
    assert "access_type=offline" in url
