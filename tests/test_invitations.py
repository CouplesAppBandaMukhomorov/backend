async def test_full_invitation_flow(client, make_couple, register, auth_headers):
    _, owner_headers, couple = await make_couple("owner@example.com")
    partner_tokens = await register("partner@example.com")
    partner_headers = auth_headers(partner_tokens)

    created = await client.post("/api/v1/invitations", headers=owner_headers)
    assert created.status_code == 201, created.text
    invitation = created.json()
    code = invitation["code"]
    assert invitation["status"] == "pending"

    active = await client.get("/api/v1/invitations/me", headers=owner_headers)
    assert active.status_code == 200
    assert active.json()["code"] == code

    preview = await client.get(f"/api/v1/invitations/{code}", headers=partner_headers)
    assert preview.status_code == 200
    assert preview.json()["inviter"]["display_name"] == "Test User"

    accepted = await client.post(f"/api/v1/invitations/{code}/accept", headers=partner_headers)
    assert accepted.status_code == 200, accepted.text
    members = accepted.json()["couple"]["members"]
    assert len(members) == 2

    owner_view = await client.get("/api/v1/couples/me", headers=owner_headers)
    assert len(owner_view.json()["members"]) == 2

    again = await client.post("/api/v1/invitations", headers=owner_headers)
    assert again.status_code == 409
    assert again.json()["code"] == "couple_is_full"


async def test_invitation_requires_couple(client, register, auth_headers):
    tokens = await register("lonely@example.com")

    response = await client.post("/api/v1/invitations", headers=auth_headers(tokens))
    assert response.status_code == 409
    assert response.json()["code"] == "couple_required"


async def test_inviter_cannot_accept_own_invitation(client, make_couple, auth_headers):
    _, owner_headers, _ = await make_couple("owner@example.com")
    created = await client.post("/api/v1/invitations", headers=owner_headers)
    code = created.json()["code"]

    response = await client.post(f"/api/v1/invitations/{code}/accept", headers=owner_headers)
    assert response.status_code == 400
    assert response.json()["code"] == "cannot_accept_own_invitation"


async def test_user_in_couple_cannot_accept_another(client, make_couple, register, auth_headers):
    _, owner_headers, _ = await make_couple("owner@example.com")
    taken_tokens = await register("taken@example.com")
    taken_headers = auth_headers(taken_tokens)
    await client.post("/api/v1/couples", json={}, headers=taken_headers)

    created = await client.post("/api/v1/invitations", headers=owner_headers)
    code = created.json()["code"]

    response = await client.post(f"/api/v1/invitations/{code}/accept", headers=taken_headers)
    assert response.status_code == 409
    assert response.json()["code"] == "already_in_couple"


async def test_inviter_can_cancel_invitation(client, make_couple, auth_headers):
    _, owner_headers, _ = await make_couple("owner@example.com")
    created = await client.post("/api/v1/invitations", headers=owner_headers)
    code = created.json()["code"]

    response = await client.delete(f"/api/v1/invitations/{code}", headers=owner_headers)
    assert response.status_code == 204

    preview = await client.get(f"/api/v1/invitations/{code}", headers=owner_headers)
    assert preview.json()["status"] == "cancelled"

    active = await client.get("/api/v1/invitations/me", headers=owner_headers)
    assert active.json() is None


async def test_only_inviter_can_cancel(client, make_couple, register, auth_headers):
    _, owner_headers, _ = await make_couple("owner@example.com")
    other_tokens = await register("other@example.com")
    created = await client.post("/api/v1/invitations", headers=owner_headers)
    code = created.json()["code"]

    response = await client.delete(
        f"/api/v1/invitations/{code}",
        headers=auth_headers(other_tokens),
    )
    assert response.status_code == 403
    assert response.json()["code"] == "not_inviter"


async def test_unknown_invitation_code(client, register, auth_headers):
    tokens = await register("someone@example.com")

    response = await client.get(
        "/api/v1/invitations/DOESNOTEXIST",
        headers=auth_headers(tokens),
    )
    assert response.status_code == 404
    assert response.json()["code"] == "invitation_not_found"
