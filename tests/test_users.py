from httpx import AsyncClient

ME_URL = "/api/v1/users/me"


class TestGetMe:
    async def test_me_returns_current_user(self, client: AsyncClient, user_credentials: dict):
        headers = {"Authorization": f"Bearer {user_credentials['access_token']}"}
        resp = await client.get(ME_URL, headers=headers)

        assert resp.status_code == 200
        body = resp.json()
        assert body["email"] == user_credentials["email"]
        assert body["is_active"] is True
        assert "id" in body

    async def test_me_without_token_returns_unauthorized(self, client: AsyncClient):
        resp = await client.get(ME_URL)
        assert resp.status_code == 401

    async def test_me_with_invalid_token_returns_unauthorized(self, client: AsyncClient):
        headers = {"Authorization": "Bearer invalid.jwt.token"}
        resp = await client.get(ME_URL, headers=headers)

        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid or expired token"

    async def test_me_with_refresh_token_returns_unauthorized(self, client: AsyncClient, user_credentials: dict):
        headers = {"Authorization": f"Bearer {user_credentials['refresh_token']}"}
        resp = await client.get(ME_URL, headers=headers)

        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid or expired token"
