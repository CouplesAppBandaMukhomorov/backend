from datetime import date, timedelta


async def test_create_couple_and_read_it(client, make_couple, auth_headers):
    tokens, headers, couple = await make_couple("owner@example.com")

    assert len(couple["members"]) == 1
    assert couple["calendar"] is None

    response = await client.get("/api/v1/couples/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["id"] == couple["id"]


async def test_user_cannot_create_two_couples(client, make_couple, auth_headers):
    _, headers, _ = await make_couple("owner@example.com")

    response = await client.post("/api/v1/couples", json={}, headers=headers)
    assert response.status_code == 409
    assert response.json()["code"] == "already_in_couple"


async def test_couple_requires_membership(client, register, auth_headers):
    tokens = await register("lonely@example.com")

    response = await client.get("/api/v1/couples/me", headers=auth_headers(tokens))
    assert response.status_code == 404
    assert response.json()["code"] == "couple_not_found"


async def test_together_since_drives_days_together(client, make_couple, auth_headers):
    _, headers, _ = await make_couple("owner@example.com")
    together_since = date.today() - timedelta(days=365)

    response = await client.patch(
        "/api/v1/couples/me",
        json={"together_since": together_since.isoformat(), "title": "Us", "timezone": "Europe/Moscow"},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["days_together"] == 365
    assert body["title"] == "Us"
    assert body["timezone"] == "Europe/Moscow"


async def test_leave_couple_dissolves_it(client, make_couple, auth_headers):
    _, headers, _ = await make_couple("owner@example.com")

    response = await client.delete("/api/v1/couples/me", headers=headers)
    assert response.status_code == 204

    check = await client.get("/api/v1/couples/me", headers=headers)
    assert check.status_code == 404


async def test_update_couple_rejects_null_timezone(client, make_couple, auth_headers):
    _, headers, _ = await make_couple("owner@example.com")

    response = await client.patch(
        "/api/v1/couples/me",
        json={"timezone": None},
        headers=headers,
    )
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
