import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.repositories.password_reset_repository import PasswordResetTokenRepository
from app.repositories.user_repository import UserRepository
from app.schemas.password_reset import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
)
from app.schemas.token import Token
from app.schemas.user import UserCreate, UserLogin


class AuthService:
    def __init__(self, db: AsyncSession):
        self.repo = UserRepository(db)
        self.reset_token_repo = PasswordResetTokenRepository(db)

    async def register(self, data: UserCreate) -> Token:
        if await self.repo.get_by_email(data.email):
            raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
        user = await self.repo.create(data.email, hash_password(data.password))
        return Token(
            access_token=create_access_token(user.id),
            refresh_token=create_refresh_token(user.id),
        )

    async def login(self, data: UserLogin) -> Token:
        user = await self.repo.get_by_email(data.email)
        if not user or not verify_password(data.password, user.hashed_password):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
        return Token(
            access_token=create_access_token(user.id),
            refresh_token=create_refresh_token(user.id),
        )

    async def refresh(self, refresh_token: str) -> Token:
        try:
            payload = decode_token(refresh_token)
            if payload.get("type") != "refresh":
                raise ValueError
            user_id = payload["sub"]
        except (JWTError, ValueError, KeyError):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")

        user = await self.repo.get_by_id(user_id)
        if not user:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
        return Token(
            access_token=create_access_token(user.id),
            refresh_token=create_refresh_token(user.id),
        )

    async def forgot_password(self, data: ForgotPasswordRequest) -> ForgotPasswordResponse:
        user = await self.repo.get_by_email(data.email)
        if not user:
            return ForgotPasswordResponse(message="If that email is registered, you will receive a password reset link")

        raw_token = secrets.token_urlsafe(32)
        hashed_token = hashlib.sha256(raw_token.encode()).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.RESET_TOKEN_EXPIRE_HOURS)

        await self.reset_token_repo.create(user.id, hashed_token, expires_at)

        return ForgotPasswordResponse(
            message=f"If that email is registered, you will receive a password reset link"
        )

    async def reset_password(self, data: ResetPasswordRequest) -> ResetPasswordResponse:
        hashed_token = hashlib.sha256(data.token.encode()).hexdigest()
        reset_token = await self.reset_token_repo.get_valid(hashed_token)

        if not reset_token:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired reset token")

        user = await self.repo.get_by_id(reset_token.user_id)
        if not user:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired reset token")

        await self.repo.update_password(user, hash_password(data.password))
        await self.reset_token_repo.mark_as_used(reset_token)

        return ResetPasswordResponse(message="Password has been reset successfully")