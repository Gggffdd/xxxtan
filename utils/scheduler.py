"""
⏰ Планировщик фоновых задач
- Проверка истёкших подписок
- Авто-напоминания за 3 дня до конца
- Деактивация просроченных подписок в VPN панели
"""
import asyncio
import logging
from datetime import datetime
from aiogram import Bot
from database.db import get_expiring_soon, get_active_subscription, deactivate_subscription
from services.xray_service import xray_service
import aiosqlite
from config import DATABASE_PATH, ADMIN_IDS

logger = logging.getLogger(__name__)


async def check_expired_subscriptions(bot: Bot):
    """Деактивирует просроченные подписки"""
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            "SELECT id, user_id, xray_email FROM subscriptions "
            "WHERE status = 'active' AND expires_at < ?", (now,)
        ) as cur:
            expired = await cur.fetchall()

    for sub_id, user_id, xray_email in expired:
        # Деактивируем в VPN панели
        if xray_email and not xray_email.startswith("pending_"):
            await xray_service.remove_client(xray_email)

        # Деактивируем в БД
        await deactivate_subscription(sub_id)

        # Уведомляем пользователя
        try:
            await bot.send_message(
                user_id,
                "⚠️ <b>Ваша подписка истекла!</b>\n\n"
                "VPN отключён. Продлите подписку для восстановления доступа.\n\n"
                "👇 Нажмите /start для продления",
                parse_mode="HTML"
            )
        except Exception:
            pass

    if expired:
        logger.info(f"🔴 Деактивировано {len(expired)} просроченных подписок")


async def send_expiry_reminders(bot: Bot):
    """Отправляет напоминания за 3 дня до конца"""
    expiring = await get_expiring_soon(3)
    for sub in expiring:
        exp = datetime.fromisoformat(sub["expires_at"])
        days = (exp - datetime.now()).days
        # Отправляем только за 3 дня или за 1 день
        if days not in (3, 1):
            continue
        try:
            await bot.send_message(
                sub["user_id"],
                f"⏰ <b>Напоминание о подписке</b>\n\n"
                f"Осталось <b>{days} {'день' if days == 1 else 'дня'}</b>!\n"
                f"Продлите VPN заранее, чтобы не потерять доступ.\n\n"
                f"📱 /start → 🛡 Купить VPN",
                parse_mode="HTML"
            )
        except Exception:
            pass


async def run_scheduler(bot: Bot):
    """Запускает планировщик — проверяет каждые 30 минут"""
    while True:
        try:
            await check_expired_subscriptions(bot)
            await send_expiry_reminders(bot)
        except Exception as e:
            logger.error(f"Ошибка планировщика: {e}")
        await asyncio.sleep(1800)  # каждые 30 минут
