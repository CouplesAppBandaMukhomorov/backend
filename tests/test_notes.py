import uuid

import pytest_asyncio
from sqlalchemy import func, select

from app.models.note import Note


@pytest_asyncio.fixture
async def paired_couple(client, make_couple, register, auth_headers):
    async def _make(
        owner_email: str = "owner@example.com",
        partner_email: str = "partner@example.com",
    ) -> dict:
        owner_tokens, owner_headers, _ = await make_couple(owner_email)
        partner_tokens = await register(partner_email)
        partner_headers = auth_headers(partner_tokens)
        invitation = await client.post("/api/v1/invitations", headers=owner_headers)
        accepted = await client.post(
            f"/api/v1/invitations/{invitation.json()['code']}/accept",
            headers=partner_headers,
        )
        assert accepted.status_code == 200, accepted.text
        return {
            "owner_tokens": owner_tokens,
            "owner_headers": owner_headers,
            "partner_tokens": partner_tokens,
            "partner_headers": partner_headers,
            "couple": accepted.json()["couple"],
        }

    return _make


async def create_note(client, headers, content: str, **extra) -> dict:
    payload = {"content": content, **extra}
    response = await client.post("/api/v1/couple/notes", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def list_contents(client, headers, **params) -> list[str]:
    response = await client.get("/api/v1/couple/notes", headers=headers, params=params)
    assert response.status_code == 200, response.text
    return [note["content"] for note in response.json()]


async def test_create_read_update_delete_note(client, paired_couple):
    pair = await paired_couple()
    headers = pair["owner_headers"]

    created = await create_note(client, headers, "Купить билеты", title="Театр")
    assert created["title"] == "Театр"
    assert created["pinned"] is False
    assert created["created_by"]["display_name"] == "Test User"

    fetched = await client.get(f"/api/v1/couple/notes/{created['id']}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["content"] == "Купить билеты"

    updated = await client.patch(
        f"/api/v1/couple/notes/{created['id']}",
        json={"content": "Купить билеты на субботу", "pinned": True},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["content"] == "Купить билеты на субботу"
    assert updated.json()["pinned"] is True

    deleted = await client.delete(f"/api/v1/couple/notes/{created['id']}", headers=headers)
    assert deleted.status_code == 204
    assert deleted.content == b""

    missing = await client.get(f"/api/v1/couple/notes/{created['id']}", headers=headers)
    assert missing.status_code == 404
    assert missing.json()["code"] == "note_not_found"


async def test_both_partners_have_equal_rights(client, paired_couple):
    pair = await paired_couple()
    owner_headers = pair["owner_headers"]
    partner_headers = pair["partner_headers"]

    created_by_owner = await create_note(client, owner_headers, "Заметка партнёра")
    assert await list_contents(client, partner_headers) == ["Заметка партнёра"]

    created_by_partner = await create_note(client, partner_headers, "Заметка второго")
    assert set(await list_contents(client, owner_headers)) == {
        "Заметка партнёра",
        "Заметка второго",
    }

    edited = await client.patch(
        f"/api/v1/couple/notes/{created_by_owner['id']}",
        json={"content": "Правка от партнёра"},
        headers=partner_headers,
    )
    assert edited.status_code == 200
    assert edited.json()["content"] == "Правка от партнёра"

    deleted = await client.delete(
        f"/api/v1/couple/notes/{created_by_partner['id']}",
        headers=owner_headers,
    )
    assert deleted.status_code == 204


async def test_notes_are_isolated_between_couples(client, paired_couple):
    first = await paired_couple("a@example.com", "b@example.com")
    second = await paired_couple("c@example.com", "d@example.com")

    note = await create_note(client, first["owner_headers"], "Только для первой пары")

    for headers in (second["owner_headers"], second["partner_headers"]):
        read = await client.get(f"/api/v1/couple/notes/{note['id']}", headers=headers)
        assert read.status_code == 404
        assert read.json()["code"] == "note_not_found"

        patched = await client.patch(
            f"/api/v1/couple/notes/{note['id']}",
            json={"content": "чужая правка"},
            headers=headers,
        )
        assert patched.status_code == 404

        deleted = await client.delete(f"/api/v1/couple/notes/{note['id']}", headers=headers)
        assert deleted.status_code == 404

    assert await list_contents(client, second["owner_headers"]) == []

    survivors = await list_contents(client, first["owner_headers"])
    assert survivors == ["Только для первой пары"]


async def test_pinned_notes_go_first_then_recent(client, paired_couple):
    pair = await paired_couple()
    headers = pair["owner_headers"]

    await create_note(client, headers, "oldest")
    middle = await create_note(client, headers, "middle")
    await create_note(client, headers, "newest")

    assert await list_contents(client, headers) == ["newest", "middle", "oldest"]

    pinned = await client.patch(
        f"/api/v1/couple/notes/{middle['id']}",
        json={"pinned": True},
        headers=headers,
    )
    assert pinned.status_code == 200
    assert await list_contents(client, headers) == ["middle", "newest", "oldest"]

    unpinned = await client.patch(
        f"/api/v1/couple/notes/{middle['id']}",
        json={"pinned": False},
        headers=headers,
    )
    assert unpinned.status_code == 200
    assert await list_contents(client, headers) == ["middle", "newest", "oldest"]


async def test_editing_moves_note_to_top(client, paired_couple):
    pair = await paired_couple()
    headers = pair["owner_headers"]

    first = await create_note(client, headers, "first")
    await create_note(client, headers, "second")

    assert await list_contents(client, headers) == ["second", "first"]

    edited = await client.patch(
        f"/api/v1/couple/notes/{first['id']}",
        json={"content": "first edited"},
        headers=headers,
    )
    assert edited.status_code == 200
    assert await list_contents(client, headers) == ["first edited", "second"]


async def test_pagination_with_limit_and_offset(client, paired_couple):
    pair = await paired_couple()
    headers = pair["owner_headers"]

    for index in range(5):
        await create_note(client, headers, f"note-{index}")

    full = await list_contents(client, headers)
    assert len(full) == 5

    page_one = await list_contents(client, headers, limit=2, offset=0)
    page_two = await list_contents(client, headers, limit=2, offset=2)
    page_three = await list_contents(client, headers, limit=2, offset=4)

    assert [len(page_one), len(page_two), len(page_three)] == [2, 2, 1]
    assert page_one + page_two + page_three == full

    beyond = await list_contents(client, headers, limit=2, offset=10)
    assert beyond == []


async def test_limit_is_validated(client, paired_couple):
    pair = await paired_couple()
    headers = pair["owner_headers"]

    too_big = await client.get("/api/v1/couple/notes", headers=headers, params={"limit": 101})
    assert too_big.status_code == 422

    negative = await client.get("/api/v1/couple/notes", headers=headers, params={"offset": -1})
    assert negative.status_code == 422


async def test_empty_patch_is_rejected(client, paired_couple):
    pair = await paired_couple()
    headers = pair["owner_headers"]
    note = await create_note(client, headers, "Заметка")

    response = await client.patch(
        f"/api/v1/couple/notes/{note['id']}",
        json={},
        headers=headers,
    )
    assert response.status_code == 400
    assert response.json()["code"] == "empty_update"


async def test_null_content_and_pinned_are_rejected(client, paired_couple):
    pair = await paired_couple()
    headers = pair["owner_headers"]
    note = await create_note(client, headers, "Заметка")

    for payload in ({"content": None}, {"pinned": None}):
        response = await client.patch(
            f"/api/v1/couple/notes/{note['id']}",
            json=payload,
            headers=headers,
        )
        assert response.status_code == 422, payload
        assert response.json()["code"] == "validation_error"


async def test_title_can_be_cleared(client, paired_couple):
    pair = await paired_couple()
    headers = pair["owner_headers"]
    note = await create_note(client, headers, "Заметка", title="Заголовок")

    response = await client.patch(
        f"/api/v1/couple/notes/{note['id']}",
        json={"title": None},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["title"] is None


async def test_empty_content_is_rejected_on_create(client, paired_couple):
    pair = await paired_couple()

    response = await client.post(
        "/api/v1/couple/notes",
        json={"content": ""},
        headers=pair["owner_headers"],
    )
    assert response.status_code == 422


async def test_author_is_tracked(client, paired_couple):
    pair = await paired_couple()
    owner_headers = pair["owner_headers"]
    partner_headers = pair["partner_headers"]

    note = await create_note(client, owner_headers, "Заметка")
    assert note["created_by"]["id"] == pair["couple"]["members"][0]["id"]
    assert note["updated_by"]["id"] == pair["couple"]["members"][0]["id"]

    edited = await client.patch(
        f"/api/v1/couple/notes/{note['id']}",
        json={"content": "Правка"},
        headers=partner_headers,
    )
    assert edited.status_code == 200
    assert edited.json()["created_by"]["id"] == pair["couple"]["members"][0]["id"]
    assert edited.json()["updated_by"]["id"] == pair["couple"]["members"][1]["id"]


async def test_notes_require_a_couple(client, register, auth_headers):
    tokens = await register("lonely@example.com")

    response = await client.get("/api/v1/couple/notes", headers=auth_headers(tokens))
    assert response.status_code == 404
    assert response.json()["code"] == "couple_not_found"


async def test_invalid_note_id_is_rejected(client, paired_couple):
    pair = await paired_couple()

    response = await client.get("/api/v1/couple/notes/not-a-uuid", headers=pair["owner_headers"])
    assert response.status_code == 422


async def test_leaving_partner_keeps_couple_notes(client, paired_couple):
    pair = await paired_couple()
    await create_note(client, pair["owner_headers"], "Остаётся в паре")

    left = await client.delete("/api/v1/couples/me", headers=pair["partner_headers"])
    assert left.status_code == 204

    assert await list_contents(client, pair["owner_headers"]) == ["Остаётся в паре"]


async def test_dissolving_couple_removes_notes(client, paired_couple, session_factory):
    pair = await paired_couple()
    await create_note(client, pair["owner_headers"], "Исчезнет вместе с парой")

    await client.delete("/api/v1/couples/me", headers=pair["partner_headers"])
    await client.delete("/api/v1/couples/me", headers=pair["owner_headers"])

    gone = await client.get("/api/v1/couple/notes", headers=pair["owner_headers"])
    assert gone.status_code == 404

    async with session_factory() as session:
        remaining = await session.scalar(select(func.count()).select_from(Note))
    assert remaining == 0


async def test_unknown_note_id_returns_not_found(client, paired_couple):
    pair = await paired_couple()

    response = await client.delete(
        f"/api/v1/couple/notes/{uuid.uuid4()}",
        headers=pair["owner_headers"],
    )
    assert response.status_code == 404
    assert response.json()["code"] == "note_not_found"


async def test_blank_content_is_rejected(client, paired_couple):
    pair = await paired_couple()
    headers = pair["owner_headers"]

    for payload in ({"content": "   "}, {"content": "\n\t "}):
        response = await client.post("/api/v1/couple/notes", json=payload, headers=headers)
        assert response.status_code == 422, payload
        assert response.json()["code"] == "validation_error"

    note = await create_note(client, headers, "Заметка")
    patched = await client.patch(
        f"/api/v1/couple/notes/{note['id']}",
        json={"content": "  "},
        headers=headers,
    )
    assert patched.status_code == 422


async def test_title_is_trimmed_and_blank_title_becomes_null(client, paired_couple):
    pair = await paired_couple()
    headers = pair["owner_headers"]

    created = await create_note(client, headers, "Заметка", title="  Поездка  ")
    assert created["title"] == "Поездка"

    blank = await create_note(client, headers, "Вторая заметка", title="   ")
    assert blank["title"] is None

    cleared = await client.patch(
        f"/api/v1/couple/notes/{created['id']}",
        json={"title": "  "},
        headers=headers,
    )
    assert cleared.status_code == 200
    assert cleared.json()["title"] is None


async def test_content_keeps_internal_formatting(client, paired_couple):
    pair = await paired_couple()
    headers = pair["owner_headers"]

    text = "План:\n  1. Билеты\n  2. Отель\n\n"
    note = await create_note(client, headers, text)
    assert note["content"] == text

    fetched = await client.get(f"/api/v1/couple/notes/{note['id']}", headers=headers)
    assert fetched.json()["content"] == text
