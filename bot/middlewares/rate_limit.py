"""
Simple in-memory rate-limit middleware.

Prevents a single user from spamming commands.
Default: max 10 requests per 5 seconds per user.
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

_WINDOW = 5.0        # seconds
_MAX_REQUESTS = 10   # per window


class RateLimitMiddleware(BaseMiddleware):
    def __init__(self, window: float = _WINDOW, max_requests: int = _MAX_REQUESTS) -> None:
        self._window = window
        self._max = max_requests
        self._buckets: dict[int, list[float]] = defaultdict(list)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user_id: int | None = None
        if isinstance(event, Message) and event.from_user:
            user_id = event.from_user.id

        if user_id is not None:
            now = time.monotonic()
            bucket = self._buckets[user_id]
            # Remove timestamps outside the window
            self._buckets[user_id] = [t for t in bucket if now - t < self._window]

            if len(self._buckets[user_id]) >= self._max:
                if isinstance(event, Message):
                    await event.answer(
                        "⚠️ You're sending requests too fast. Please wait a moment."
                    )
                return None  # Drop the update

            self._buckets[user_id].append(now)

        return await handler(event, data)
