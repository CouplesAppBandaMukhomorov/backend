import httpx
import pytest
import respx

from tests.conftest import GOOGLE_CLIENT_ID, PASSWORD


async def test_register_returns_tokens_and_profile(client, register, auth_headers):
    tokens = await register("alice@example.com", display_name="Alice")

    assert tokens["token_type"] == "bearer"
    assert tokens["access_token"]
    assert tokens["refresh_token"]

    response = await client.get("/api/v1/users/me", headers=auth_headers(tokens))
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "alice@example.com"
    assert body["display_name"] == "Alice"


async def test_register_rejects_duplicate_email(client, register):
    await register("alice@example.com")

    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "alice@example.com", "password": PASSWORD, "display_name": "Other"},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "email_already_registered"


async def test_login_success_and_failure(client, register):
    await register("alice@example.com")

    ok = await client.post(
        "/api/v1/auth/login",
        json={"email": "alice@example.com", "password": PASSWORD},
    )
    assert ok.status_code == 200
    assert ok.json()["access_token"]

    bad = await client.post(
        "/api/v1/auth/login",
        json={"email": "alice@example.com", "password": "wrong-password"},
    )
    assert bad.status_code == 401
    assert bad.json()["code"] == "invalid_credentials"


async def test_refresh_issues_new_tokens(client, register):
    tokens = await register("alice@example.com")

    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert response.status_code == 200
    assert response.json()["access_token"]


async def test_refresh_rejects_access_token(client, register):
    tokens = await register("alice@example.com")

    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["access_token"]},
    )
    assert response.status_code == 401


async def test_me_requires_token(client):
    response = await client.get("/api/v1/users/me")
    assert response.status_code == 401
    assert response.json()["code"] == "missing_token"


async def test_update_profile(client, register, auth_headers):
    tokens = await register("alice@example.com")

    response = await client.patch(
        "/api/v1/users/me",
        json={"display_name": "Alice Cooper"},
        headers=auth_headers(tokens),
    )
    assert response.status_code == 200
    assert response.json()["display_name"] == "Alice Cooper"


async def test_update_profile_rejects_null_display_name(client, register, auth_headers):
    tokens = await register("alice@example.com")

    response = await client.patch(
        "/api/v1/users/me",
        json={"display_name": None},
        headers=auth_headers(tokens),
    )
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


async def test_update_profile_allows_clearing_avatar(client, register, auth_headers):
    tokens = await register("alice@example.com")
    headers = auth_headers(tokens)

    filled = await client.patch(
        "/api/v1/users/me",
        json={"avatar_url": "https://example.com/avatar.png"},
        headers=headers,
    )
    assert filled.status_code == 200
    assert filled.json()["avatar_url"] == "https://example.com/avatar.png"

    cleared = await client.patch("/api/v1/users/me", json={"avatar_url": None}, headers=headers)
    assert cleared.status_code == 200
    assert cleared.json()["avatar_url"] is None


async def test_google_login_creates_user(client):
    with respx.mock(assert_all_called=False) as router:
        router.get("https://oauth2.googleapis.com/tokeninfo").mock(
            return_value=httpx.Response(
                200,
                json={
                    "aud": GOOGLE_CLIENT_ID,
                    "sub": "google-sub-123",
                    "email": "bob@example.com",
                    "email_verified": "true",
                    "name": "Bob",
                },
            )
        )
        response = await client.post("/api/v1/auth/google", json={"id_token": "fake-id-token"})

    assert response.status_code == 200, response.text
    assert response.json()["access_token"]


async def test_google_login_rejects_unverified_email(client):
    with respx.mock(assert_all_called=False) as router:
        router.get("https://oauth2.googleapis.com/tokeninfo").mock(
            return_value=httpx.Response(
                200,
                json={
                    "aud": GOOGLE_CLIENT_ID,
                    "sub": "google-sub-123",
                    "email": "bob@example.com",
                    "email_verified": "false",
                },
            )
        )
        response = await client.post("/api/v1/auth/google", json={"id_token": "fake-id-token"})

    assert response.status_code == 400
    assert response.json()["code"] == "google_email_not_verified"


async def test_google_login_rejects_foreign_audience(client):
    with respx.mock(assert_all_called=False) as router:
        router.get("https://oauth2.googleapis.com/tokeninfo").mock(
            return_value=httpx.Response(
                200,
                json={
                    "aud": "some-other-application",
                    "sub": "google-sub-999",
                    "email": "attacker@example.com",
                    "email_verified": "true",
                },
            )
        )
        response = await client.post("/api/v1/auth/google", json={"id_token": "foreign-token"})

    assert response.status_code == 400
    assert response.json()["code"] == "invalid_google_token"


@pytest.mark.parametrize("token", ["", "not-a-jwt"])
async def test_me_rejects_invalid_token(client, token):
    response = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401
