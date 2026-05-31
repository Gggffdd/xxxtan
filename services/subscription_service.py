"""Сервис управления подписками — связующее звено между ботом, БД и VPN"""

import logging
from datetime import datetime
from config import PLANS, REFERRAL_BONUS_DAYS, REFERRAL_ENABLED
from database.db import (
    create_subscription, get_active_subscription, extend_subscription,
    deactivate_subscription, confirm_payment, add_balance,
    get_user, get_user_referrals
)
from services.xray_service import xray_service

logger = logging.getLogger(__name__)


async def activate_subscription(user_id: int, plan_key: str, payment_id: int,
                                 charge_id: str = None, bonus_days: int = 0) -> dict | None:
    """
    Полный цикл активации подписки:
    1. Подтверждаем платёж в БД
    2. Создаём клиента в 3x-ui VPN панели
    3. Сохраняем подписку в БД
    4. Начисляем бонус рефереру
    Возвращает данные подписки или None при ошибке.
    """
    plan = PLANS.get(plan_key)
    if not plan:
        logger.error(f"Неизвестный тариф: {plan_key}")
        return None

    # Подтверждаем платёж
    await confirm_payment(payment_id, charge_id)

    total_days = plan["days"] + bonus_days

    # Создаём клиента в VPN панели
    client = await xray_service.add_client(user_id, total_days, plan["gb"])

    if not client:
        # VPN панель недоступна — создаём заглушку
        logger.warning(f"⚠️ 3x-ui недоступна для user {user_id}, создаём placeholder")
        client = {
            "client_id": f"pending_{user_id}_{int(datetime.now().timestamp())}",
            "email": f"pending_{user_id}",
            "config_link": "⏳ Конфиг будет готов в течение 1 часа. Обратитесь в поддержку."
        }

    # Сохраняем в БД
    await create_subscription(
        user_id=user_id,
        plan_key=plan_key,
        xray_client_id=client["client_id"],
        xray_email=client["email"],
        config_link=client["config_link"],
        days=total_days,
        gb=plan["gb"]
    )

    # Бонус рефереру
    if REFERRAL_ENABLED:
        await _give_referral_bonus(user_id)

    logger.info(f"✅ Подписка {plan_key} активирована для user {user_id}")
    return client


async def cancel_subscription(user_id: int) -> bool:
    """Отменяет активную подписку пользователя"""
    sub = await get_active_subscription(user_id)
    if not sub:
        return False

    # Удаляем из VPN панели
    if sub.get("xray_email") and not sub["xray_email"].startswith("pending_"):
        await xray_service.remove_client(sub["xray_email"])

    await deactivate_subscription(sub["id"])
    return True


async def renew_subscription(user_id: int, plan_key: str, payment_id: int,
                              charge_id: str = None) -> dict | None:
    """Продлевает существующую подписку"""
    plan = PLANS.get(plan_key)
    if not plan:
        return None

    sub = await get_active_subscription(user_id)

    await confirm_payment(payment_id, charge_id)

    if sub and sub.get("xray_email") and not sub["xray_email"].startswith("pending_"):
        # Продлеваем в 3x-ui
        ok = await xray_service.extend_client(sub["xray_email"], plan["days"])
        if ok:
            await extend_subscription(sub["id"], plan["days"])
            return {"config_link": sub["config_link"], "extended": True}

    # Если продление не удалось — создаём новую подписку
    return await activate_subscription(user_id, plan_key, payment_id, charge_id)


async def get_subscription_info(user_id: int) -> dict | None:
    """Получает полную инфу о подписке включая статистику трафика"""
    sub = await get_active_subscription(user_id)
    if not sub:
        return None

    stats = None
    if sub.get("xray_email") and not sub["xray_email"].startswith("pending_"):
        stats = await xray_service.get_client_stats(sub["xray_email"])

    expires = datetime.fromisoformat(sub["expires_at"])
    days_left = (expires - datetime.now()).days

    return {
        **sub,
        "days_left": max(0, days_left),
        "is_expired": days_left <= 0,
        "stats": stats,
    }


async def _give_referral_bonus(referred_user_id: int):
    """Начисляет бонус рефереру после первой оплаты"""
    try:
        from database.db import get_user
        import aiosqlite
        from config import DATABASE_PATH
        async with aiosqlite.connect(DATABASE_PATH) as db:
            # Проверяем — был ли уже бонус
            async with db.execute(
                "SELECT * FROM referrals WHERE referred_id = ? AND bonus_given = 0",
                (referred_user_id,)
            ) as cur:
                ref_row = await cur.fetchone()
            if ref_row:
                referrer_id = ref_row[1]
                # Продлеваем подписку реферера
                ref_sub = await get_active_subscription(referrer_id)
                if ref_sub:
                    await extend_subscription(ref_sub["id"], REFERRAL_BONUS_DAYS)
                    if ref_sub.get("xray_email"):
                        await xray_service.extend_client(ref_sub["xray_email"], REFERRAL_BONUS_DAYS)
                # Помечаем бонус выданным
                await db.execute(
                    "UPDATE referrals SET bonus_given = 1 WHERE referred_id = ?",
                    (referred_user_id,)
                )
                await db.commit()
                logger.info(f"🎁 Бонус +{REFERRAL_BONUS_DAYS} дней выдан рефереру {referrer_id}")
    except Exception as e:
        logger.error(f"Ошибка реферального бонуса: {e}")
