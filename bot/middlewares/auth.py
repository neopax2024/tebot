"""
Authentication middleware.

• Registers / refreshes the user record on every update.
• Rejects banned users.
• Injects `user` into handler data so handlers can use it without extra DB calls.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

from database.engine import AsyncSessionLocal
from database import operations as ops


class AuthMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        # Extract Telegram user from the update
        tg_user = None
        if hasattr(event, "from_user"):
            tg_user = event.from_user
        elif isinstance(event, Update):
            for attr in ("message", "callback_query", "inline_query"):
                sub = getattr(event, attr, None)
                if sub and hasattr(sub, "from_user"):
                    tg_user = sub.from_user
                    break

        if tg_user is None:
            return await handler(event, data)

        async with AsyncSessionLocal() as session:
            user, _ = await ops.get_or_create_user(
                session=session,
                telegram_id=tg_user.id,
                username=tg_user.username,
                first_name=tg_user.first_name,
                last_name=tg_user.last_name,
                language_code=tg_user.language_code or "en",
            )

            if user.is_banned:
                # Silently drop updates from banned users
                return None

            data["db_user"] = user

        return await handler(event, data)
