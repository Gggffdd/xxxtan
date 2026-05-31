import logging
from typing import Callable, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject
from database.db import get_user

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any]
    ) -> Any:
        if hasattr(event, 'from_user') and event.from_user:
            uid = event.from_user.id
            logger.info(f"📨 [{uid}] @{event.from_user.username}: {getattr(event, 'text', '')[:50]}")
            user = await get_user(uid)
            if user and user.get("is_banned"):
                await event.answer("⛔ Вы заблокированы.")
                return
        return await handler(event, data)
