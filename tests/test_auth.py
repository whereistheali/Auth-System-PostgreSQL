from httpx import AsyncClient


REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
REFRESH_URL = "/api/v1/auth/refresh"


class TestRegister:
    async def test_register_returns_tokens(self, client: AsyncClient):
        payload = {"email": "new@example.com", "password": "StrongPass1"}
        resp = await client.post(REGISTER_URL, json=payload)

        assert resp.status_code == 201
        body = resp.json()
        assert body["token_type"] == "bearer"
        assert len(body["access_token"]) > 0
        assert len(body["refresh_token"]) > 0

    async def test_register_duplicate_email_returns_conflict(self, client: AsyncClient, user_credentials: dict):
        payload = {"email": user_credentials["email"], "password": "StrongPass1"}
        resp = await client.post(REGISTER_URL, json=payload)

        assert resp.status_code == 409
        assert resp.json()["detail"] == "Email already registered"

    async def test_register_invalid_email_returns_unprocessable(self, client: AsyncClient):
        payload = {"email": "not-an-email", "password": "StrongPass1"}
        resp = await client.post(REGISTER_URL, json=payload)

        assert resp.status_code == 422

    async def test_register_weak_password_returns_unprocessable(self, client: AsyncClient):
        payload = {"email": "weak@example.com", "password": "12"}
        resp = await client.post(REGISTER_URL, json=payload)

        assert resp.status_code == 201

    async def test_register_missing_fields_returns_unprocessable(self, client: AsyncClient):
        resp = await client.post(REGISTER_URL, json={})
        assert resp.status_code == 422

        resp = await client.post(REGISTER_URL, json={"email": "test@example.com"})
        assert resp.status_code == 422


class TestLogin:
    async def test_login_returns_tokens(self, client: AsyncClient, user_credentials: dict):
        payload = {"email": user_credentials["email"], "password": user_credentials["password"]}
        resp = await client.post(LOGIN_URL, json=payload)

        assert resp.status_code == 200
        body = resp.json()
        assert body["token_type"] == "bearer"
        assert len(body["access_token"]) > 0
        assert len(body["refresh_token"]) > 0

    async def test_login_wrong_password_returns_unauthorized(self, client: AsyncClient, user_credentials: dict):
        payload = {"email": user_credentials["email"], "password": "WrongPass1"}
        resp = await client.post(LOGIN_URL, json=payload)

        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid credentials"

    async def test_login_nonexistent_email_returns_unauthorized(self, client: AsyncClient):
        payload = {"email": "nonexistent@example.com", "password": "StrongPass1"}
        resp = await client.post(LOGIN_URL, json=payload)

        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid credentials"


class TestRefresh:
    async def test_refresh_returns_tokens(self, client: AsyncClient, user_credentials: dict):
        payload = {"refresh_token": user_credentials["refresh_token"]}
        resp = await client.post(REFRESH_URL, json=payload)

        assert resp.status_code == 200
        body = resp.json()
        assert body["token_type"] == "bearer"
        assert len(body["access_token"]) > 0
        assert len(body["refresh_token"]) > 0

    async def test_refresh_with_access_token_returns_unauthorized(self, client: AsyncClient, user_credentials: dict):
        payload = {"refresh_token": user_credentials["access_token"]}
        resp = await client.post(REFRESH_URL, json=payload)

        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid refresh token"

    async def test_refresh_invalid_token_returns_unauthorized(self, client: AsyncClient):
        payload = {"refresh_token": "invalid.jwt.token"}
        resp = await client.post(REFRESH_URL, json=payload)

        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid refresh token"
