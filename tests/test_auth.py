import hashlib
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.password_reset import PasswordResetToken

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
REFRESH_URL = "/api/v1/auth/refresh"
FORGOT_PASSWORD_URL = "/api/v1/auth/forgot-password"
RESET_PASSWORD_URL = "/api/v1/auth/reset-password"


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


class TestForgotPassword:
    async def test_forgot_password_existing_email_returns_success(
        self, client: AsyncClient, user_credentials: dict
    ):
        with patch("app.services.auth_service.send_password_reset_email") as mock_send:
            payload = {"email": user_credentials["email"]}
            resp = await client.post(FORGOT_PASSWORD_URL, json=payload)

            assert resp.status_code == 200
            assert resp.json()["message"] == "If that email is registered, you will receive a password reset link"
            mock_send.assert_awaited_once_with(user_credentials["email"], mock_send.call_args[0][1])

    async def test_forgot_password_nonexistent_email_returns_same_message(
        self, client: AsyncClient
    ):
        payload = {"email": "nonexistent@example.com"}
        resp = await client.post(FORGOT_PASSWORD_URL, json=payload)

        assert resp.status_code == 200
        assert resp.json()["message"] == "If that email is registered, you will receive a password reset link"

    async def test_forgot_password_invalid_email_returns_unprocessable(self, client: AsyncClient):
        payload = {"email": "not-an-email"}
        resp = await client.post(FORGOT_PASSWORD_URL, json=payload)

        assert resp.status_code == 422

    async def test_forgot_password_creates_token_in_db(
        self, client: AsyncClient, user_credentials: dict, db_session: AsyncSession
    ):
        with patch("app.services.auth_service.send_password_reset_email"):
            await client.post(FORGOT_PASSWORD_URL, json={"email": user_credentials["email"]})

        result = await db_session.execute(
            select(PasswordResetToken).where(PasswordResetToken.user_id.isnot(None))
        )
        token_record = result.scalar_one_or_none()
        assert token_record is not None
        assert token_record.is_used is False
        assert token_record.expires_at > datetime.now(timezone.utc)


class TestResetPassword:
    async def _request_reset(self, client: AsyncClient, email: str) -> str:
        with patch("app.services.auth_service.send_password_reset_email") as mock_send:
            await client.post(FORGOT_PASSWORD_URL, json={"email": email})
            return mock_send.call_args[0][1]

    async def test_reset_password_returns_success(
        self, client: AsyncClient, user_credentials: dict
    ):
        raw_token = await self._request_reset(client, user_credentials["email"])

        resp = await client.post(RESET_PASSWORD_URL, json={
            "token": raw_token,
            "password": "NewStrongPass1",
        })

        assert resp.status_code == 200
        assert resp.json()["message"] == "Password has been reset successfully"

    async def test_reset_password_updates_password(
        self, client: AsyncClient, user_credentials: dict
    ):
        raw_token = await self._request_reset(client, user_credentials["email"])

        await client.post(RESET_PASSWORD_URL, json={
            "token": raw_token,
            "password": "NewStrongPass1",
        })

        resp = await client.post("/api/v1/auth/login", json={
            "email": user_credentials["email"],
            "password": "NewStrongPass1",
        })
        assert resp.status_code == 200

        resp = await client.post("/api/v1/auth/login", json={
            "email": user_credentials["email"],
            "password": user_credentials["password"],
        })
        assert resp.status_code == 401

    async def test_reset_password_invalid_token_returns_bad_request(self, client: AsyncClient):
        resp = await client.post(RESET_PASSWORD_URL, json={
            "token": "invalid-token-that-does-not-exist",
            "password": "NewStrongPass1",
        })

        assert resp.status_code == 400
        assert resp.json()["detail"] == "Invalid or expired reset token"

    async def test_reset_password_expired_token_returns_bad_request(
        self, client: AsyncClient, user_credentials: dict, db_session: AsyncSession
    ):
        raw_token = await self._request_reset(client, user_credentials["email"])

        hashed_token = hashlib.sha256(raw_token.encode()).hexdigest()
        result = await db_session.execute(
            PasswordResetToken.__table__.select().where(PasswordResetToken.hashed_token == hashed_token)
        )
        record = result.fetchone()
        await db_session.execute(
            PasswordResetToken.__table__.update()
            .where(PasswordResetToken.hashed_token == hashed_token)
            .values(expires_at=datetime.now(timezone.utc) - timedelta(hours=1))
        )
        await db_session.commit()

        resp = await client.post(RESET_PASSWORD_URL, json={
            "token": raw_token,
            "password": "NewStrongPass1",
        })

        assert resp.status_code == 400
        assert resp.json()["detail"] == "Invalid or expired reset token"

    async def test_reset_password_used_token_returns_bad_request(
        self, client: AsyncClient, user_credentials: dict
    ):
        raw_token = await self._request_reset(client, user_credentials["email"])

        await client.post(RESET_PASSWORD_URL, json={
            "token": raw_token,
            "password": "NewStrongPass1",
        })

        resp = await client.post(RESET_PASSWORD_URL, json={
            "token": raw_token,
            "password": "AnotherPass1",
        })

        assert resp.status_code == 400
        assert resp.json()["detail"] == "Invalid or expired reset token"

    async def test_reset_password_missing_fields_returns_unprocessable(self, client: AsyncClient):
        resp = await client.post(RESET_PASSWORD_URL, json={})
        assert resp.status_code == 422

        resp = await client.post(RESET_PASSWORD_URL, json={"token": "some-token"})
        assert resp.status_code == 422

        resp = await client.post(RESET_PASSWORD_URL, json={"password": "SomePass1"})
        assert resp.status_code == 422
