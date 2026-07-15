from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.password_reset import PasswordResetToken


class PasswordResetTokenRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, user_id, hashed_token: str, expires_at: datetime) -> PasswordResetToken:
        token = PasswordResetToken(
            user_id=user_id,
            hashed_token=hashed_token,
            expires_at=expires_at,
        )
        self.db.add(token)
        await self.db.commit()
        await self.db.refresh(token)
        return token

    async def get_valid(self, hashed_token: str) -> PasswordResetToken | None:
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            select(PasswordResetToken).where(
                PasswordResetToken.hashed_token == hashed_token,
                PasswordResetToken.is_used == False,
                PasswordResetToken.expires_at > now,
            )
        )
        return result.scalar_one_or_none()

    async def mark_as_used(self, token: PasswordResetToken) -> None:
        token.is_used = True
        await self.db.commit()

    async def invalidate_user_tokens(self, user_id) -> None:
        result = await self.db.execute(
            select(PasswordResetToken).where(
                PasswordResetToken.user_id == user_id,
                PasswordResetToken.is_used == False,
            )
        )
        tokens = result.scalars().all()
        for t in tokens:
            t.is_used = True
        await self.db.commit()
