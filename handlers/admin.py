"""
👑 ПОЛНАЯ АДМИН ПАНЕЛЬ
Команда: /admin
"""
import logging
from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import ADMIN_IDS, PLANS, REFERRAL_BONUS_DAYS
from database.db import (
    get_stats, get_all_users, get_user, ban_user,
    get_active_subscription, extend_subscription, deactivate_subscription,
    create_payment, get_all_promos, create_promo, delete_promo,
    get_expiring_soon, get_active_subs_count
)
from services.subscription_service import activate_subscription, cancel_subscription
from services.xray_service import xray_service
from keyboards.keyboards import (
    admin_main_kb, admin_users_kb, admin_promos_kb,
    admin_back_kb, admin_confirm_broadcast_kb,
    admin_give_sub_plans_kb, admin_user_actions_kb
)

logger = logging.getLogger(__name__)
admin_router = Router()


# ── Фильтр только для админов ──
def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


class AdminStates(StatesGroup):
    # Промокоды
    promo_code     = State()
    promo_discount = State()
    promo_days     = State()
    promo_uses     = State()
    # Рассылка
    broadcast_text = State()
    broadcast_ready = State()
    # Поиск пользователя
    find_user_id   = State()
    # Сообщение пользователю
    msg_user_id    = State()
    msg_text       = State()
    # Удаление промокода
    del_promo_id   = State()


# ═══════════════════════════════════════
#   🚪  ВХОД В ПАНЕЛЬ
# ═══════════════════════════════════════

@admin_router.message(Command("admin"))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        return
    stats = await get_stats()
    text = (
        "👑 <b>ADMIN ПАНЕЛЬ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 Пользователей: <b>{stats['users']}</b>\n"
        f"🛡 Активных подписок: <b>{stats['active_subs']}</b>\n"
        f"💰 Выручка сегодня: <b>{stats['today_revenue']} ₽</b>\n"
        f"💵 Всего выручки: <b>{stats['total_revenue']} ₽</b>\n\n"
        f"🕒 <i>{datetime.now().strftime('%d.%m.%Y %H:%M')}</i>"
    )
    await message.answer(text, reply_markup=admin_main_kb(), parse_mode="HTML")


@admin_router.callback_query(F.data == "adm:main")
async def admin_main(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.clear()
    stats = await get_stats()
    text = (
        "👑 <b>ADMIN ПАНЕЛЬ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 Пользователей: <b>{stats['users']}</b>\n"
        f"🛡 Активных подписок: <b>{stats['active_subs']}</b>\n"
        f"💰 Выручка сегодня: <b>{stats['today_revenue']} ₽</b>\n"
        f"💵 Всего выручки: <b>{stats['total_revenue']} ₽</b>"
    )
    await call.message.edit_text(text, reply_markup=admin_main_kb(), parse_mode="HTML")
    await call.answer()


# ═══════════════════════════════════════
#   📊  СТАТИСТИКА
# ═══════════════════════════════════════

@admin_router.callback_query(F.data == "adm:stats")
async def admin_stats(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    stats = await get_stats()
    expiring = await get_expiring_soon(3)

    text = (
        "📊 <b>СТАТИСТИКА</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "👥 <b>Пользователи:</b>\n"
        f"   Всего: <b>{stats['users']}</b>\n\n"
        "🛡 <b>Подписки:</b>\n"
        f"   Активных: <b>{stats['active_subs']}</b>\n"
        f"   Истекают скоро (3 дня): <b>{len(expiring)}</b>\n\n"
        "💰 <b>Финансы:</b>\n"
        f"   Сегодня: <b>{stats['today_revenue']} ₽</b>\n"
        f"   Всего: <b>{stats['total_revenue']} ₽</b>\n\n"
        "📦 <b>Тарифы:</b>\n"
    )
    for key, plan in PLANS.items():
        text += f"   {plan['emoji']} {plan['name']}: <b>{plan['price']} ₽</b>\n"

    await call.message.edit_text(text, reply_markup=admin_back_kb(), parse_mode="HTML")
    await call.answer()


# ═══════════════════════════════════════
#   💰  ФИНАНСЫ
# ═══════════════════════════════════════

@admin_router.callback_query(F.data == "adm:finance")
async def admin_finance(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    from database.db import get_today_revenue, get_total_revenue
    today = await get_today_revenue()
    total = await get_total_revenue()

    text = (
        "💰 <b>ФИНАНСОВАЯ СТАТИСТИКА</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📅 Сегодня: <b>{today} ₽</b>\n"
        f"💵 Всего получено: <b>{total} ₽</b>\n\n"
        "📦 <b>Ценообразование:</b>\n"
    )
    for key, plan in PLANS.items():
        text += f"   {plan['emoji']} {plan['name']}: {plan['price']} ₽ / {plan['days']} дн.\n"

    await call.message.edit_text(text, reply_markup=admin_back_kb(), parse_mode="HTML")
    await call.answer()


# ═══════════════════════════════════════
#   ⚙️  СТАТУС VPN ПАНЕЛИ
# ═══════════════════════════════════════

@admin_router.callback_query(F.data == "adm:vpn_status")
async def admin_vpn_status(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    await call.answer("🔄 Проверяем подключение...")
    ok = await xray_service.check_connection()
    from config import XRAY_PANEL_URL, XRAY_INBOUND_ID

    status = "✅ Онлайн" if ok else "❌ Недоступна"
    text = (
        "⚙️ <b>VPN ПАНЕЛЬ (3x-ui)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔌 Статус: <b>{status}</b>\n"
        f"🌐 URL: <code>{XRAY_PANEL_URL}</code>\n"
        f"📍 Inbound ID: <b>{XRAY_INBOUND_ID}</b>\n\n"
        f"{'✅ Бот автоматически создаёт клиентов в панели.' if ok else '❌ Проверь настройки в config.py (XRAY_PANEL_URL, XRAY_PANEL_USER, XRAY_PANEL_PASS)'}"
    )
    await call.message.edit_text(text, reply_markup=admin_back_kb(), parse_mode="HTML")


# ═══════════════════════════════════════
#   👥  ПОЛЬЗОВАТЕЛИ
# ═══════════════════════════════════════

@admin_router.callback_query(F.data == "adm:users")
async def admin_users(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    users = await get_all_users()
    active = await get_active_subs_count()
    text = (
        "👥 <b>ПОЛЬЗОВАТЕЛИ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Всего: <b>{len(users)}</b>\n"
        f"С активной подпиской: <b>{active}</b>\n\n"
        "Что хочешь сделать?"
    )
    await call.message.edit_text(text, reply_markup=admin_users_kb(), parse_mode="HTML")
    await call.answer()


@admin_router.callback_query(F.data == "adm:find_user")
async def admin_find_user_ask(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(AdminStates.find_user_id)
    await call.message.edit_text(
        "🔍 <b>Поиск пользователя</b>\n\n"
        "Введите Telegram ID пользователя:",
        reply_markup=admin_back_kb(),
        parse_mode="HTML"
    )
    await call.answer()


@admin_router.message(AdminStates.find_user_id)
async def admin_find_user(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        uid = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите числовой ID")
        return

    user = await get_user(uid)
    if not user:
        await message.answer("❌ Пользователь не найден")
        await state.clear()
        return

    sub = await get_active_subscription(uid)
    sub_text = "Нет подписки"
    if sub:
        exp = datetime.fromisoformat(sub["expires_at"])
        days = (exp - datetime.now()).days
        sub_text = f"{PLANS.get(sub['plan_key'], {}).get('name', sub['plan_key'])} — {days} дн."

    text = (
        f"👤 <b>ПОЛЬЗОВАТЕЛЬ #{uid}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"ID: <code>{uid}</code>\n"
        f"Имя: <b>{user.get('full_name', '—')}</b>\n"
        f"Username: @{user.get('username', '—')}\n"
        f"Статус: {'⛔ Забанен' if user.get('is_banned') else '✅ Активен'}\n"
        f"Подписка: <b>{sub_text}</b>\n"
        f"Зарегистрирован: {user.get('created_at', '—')[:10]}"
    )
    is_banned = bool(user.get("is_banned"))
    await message.answer(text, reply_markup=admin_user_actions_kb(uid, is_banned), parse_mode="HTML")
    await state.clear()


@admin_router.callback_query(F.data.startswith("adm:ban:"))
async def admin_ban(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    uid = int(call.data.split(":")[2])
    await ban_user(uid, True)
    await cancel_subscription(uid)
    await call.answer(f"⛔ Пользователь {uid} забанен", show_alert=True)
    await call.message.edit_text(f"⛔ Пользователь <code>{uid}</code> заблокирован.", parse_mode="HTML",
                                  reply_markup=admin_back_kb("adm:users"))


@admin_router.callback_query(F.data.startswith("adm:unban:"))
async def admin_unban(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    uid = int(call.data.split(":")[2])
    await ban_user(uid, False)
    await call.answer(f"✅ Пользователь {uid} разбанен", show_alert=True)
    await call.message.edit_text(f"✅ Пользователь <code>{uid}</code> разблокирован.", parse_mode="HTML",
                                  reply_markup=admin_back_kb("adm:users"))


# ── Написать пользователю ──

@admin_router.callback_query(F.data.startswith("adm:msg:"))
async def admin_msg_ask(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    uid = int(call.data.split(":")[2])
    await state.update_data(msg_target=uid)
    await state.set_state(AdminStates.msg_text)
    await call.message.edit_text(
        f"📩 <b>Сообщение пользователю {uid}</b>\n\nВведи текст:",
        parse_mode="HTML", reply_markup=admin_back_kb()
    )
    await call.answer()


@admin_router.message(AdminStates.msg_text)
async def admin_send_msg(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    uid = data.get("msg_target")
    try:
        await bot.send_message(uid, f"📩 <b>Сообщение от администратора:</b>\n\n{message.text}", parse_mode="HTML")
        await message.answer(f"✅ Сообщение отправлено пользователю {uid}")
    except Exception as e:
        await message.answer(f"❌ Не удалось отправить: {e}")
    await state.clear()


# ── Выдать подписку ──

@admin_router.callback_query(F.data.startswith("adm:give_to:"))
async def admin_give_sub_choose_plan(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    uid = int(call.data.split(":")[2])
    await call.message.edit_text(
        f"🎁 <b>Выдать подписку</b>\n\nПользователь: <code>{uid}</code>\nВыбери тариф:",
        reply_markup=admin_give_sub_plans_kb(uid),
        parse_mode="HTML"
    )
    await call.answer()


@admin_router.callback_query(F.data.startswith("adm:give:"))
async def admin_give_sub(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        return
    parts = call.data.split(":")
    uid = int(parts[2])
    plan_key = parts[3]

    payment_id = await create_payment(uid, plan_key, 0, method='admin_gift')
    client = await activate_subscription(uid, plan_key, payment_id)

    if client:
        config = client.get("config_link", "")
        try:
            await bot.send_message(
                uid,
                f"🎁 <b>Вам выдана бесплатная подписка!</b>\n\n"
                f"📦 Тариф: <b>{PLANS[plan_key]['name']}</b>\n\n"
                f"🔑 Ваш ключ:\n<code>{config}</code>",
                parse_mode="HTML"
            )
        except Exception:
            pass
        await call.answer("✅ Подписка выдана!", show_alert=True)
        await call.message.edit_text(
            f"✅ Подписка <b>{PLANS[plan_key]['name']}</b> выдана пользователю <code>{uid}</code>",
            parse_mode="HTML", reply_markup=admin_back_kb("adm:users")
        )
    else:
        await call.answer("❌ Ошибка выдачи подписки", show_alert=True)


@admin_router.callback_query(F.data.startswith("adm:reset_traffic:"))
async def admin_reset_traffic(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    uid = int(call.data.split(":")[2])
    sub = await get_active_subscription(uid)
    if sub and sub.get("xray_email"):
        ok = await xray_service.reset_client_traffic(sub["xray_email"])
        await call.answer("✅ Трафик сброшен" if ok else "❌ Ошибка сброса", show_alert=True)
    else:
        await call.answer("❌ Нет активной подписки", show_alert=True)


# ═══════════════════════════════════════
#   🏷  ПРОМОКОДЫ
# ═══════════════════════════════════════

@admin_router.callback_query(F.data == "adm:promos")
async def admin_promos(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    promos = await get_all_promos()
    text = (
        "🏷 <b>ПРОМОКОДЫ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Активных промокодов: <b>{len(promos)}</b>"
    )
    await call.message.edit_text(text, reply_markup=admin_promos_kb(), parse_mode="HTML")
    await call.answer()


@admin_router.callback_query(F.data == "adm:list_promos")
async def admin_list_promos(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    promos = await get_all_promos()
    if not promos:
        text = "📋 Промокодов нет"
    else:
        lines = ["📋 <b>СПИСОК ПРОМОКОДОВ</b>\n━━━━━━━━━━━━━━━━━━\n"]
        for p in promos:
            discount = f"скидка {p['discount_pct']}%" if p['discount_pct'] else ""
            days = f"+{p['bonus_days']} дн." if p['bonus_days'] else ""
            bonus = ", ".join(filter(None, [discount, days])) or "без бонуса"
            lines.append(
                f"🏷 <code>{p['code']}</code> [ID:{p['id']}]\n"
                f"   Бонус: {bonus} | Осталось: {p['uses_left']}"
            )
        text = "\n".join(lines)

    await call.message.edit_text(text, reply_markup=admin_back_kb("adm:promos"), parse_mode="HTML")
    await call.answer()


@admin_router.callback_query(F.data == "adm:create_promo")
async def admin_create_promo_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(AdminStates.promo_code)
    await call.message.edit_text(
        "🏷 <b>СОЗДАНИЕ ПРОМОКОДА</b>\n\n"
        "Шаг 1/4 — Введи код (например: <code>SUMMER25</code>):",
        parse_mode="HTML", reply_markup=admin_back_kb("adm:promos")
    )
    await call.answer()


@admin_router.message(AdminStates.promo_code)
async def promo_get_code(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(promo_code=message.text.upper())
    await state.set_state(AdminStates.promo_discount)
    await message.answer("Шаг 2/4 — Скидка в % (0 = без скидки):")


@admin_router.message(AdminStates.promo_discount)
async def promo_get_discount(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        d = int(message.text)
    except ValueError:
        await message.answer("❌ Введи число")
        return
    await state.update_data(discount=d)
    await state.set_state(AdminStates.promo_days)
    await message.answer("Шаг 3/4 — Бонусные дни (0 = без бонуса):")


@admin_router.message(AdminStates.promo_days)
async def promo_get_days(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        d = int(message.text)
    except ValueError:
        await message.answer("❌ Введи число")
        return
    await state.update_data(bonus_days=d)
    await state.set_state(AdminStates.promo_uses)
    await message.answer("Шаг 4/4 — Сколько раз можно использовать (например: 100):")


@admin_router.message(AdminStates.promo_uses)
async def promo_get_uses(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        uses = int(message.text)
    except ValueError:
        await message.answer("❌ Введи число")
        return

    data = await state.get_data()
    ok = await create_promo(data["promo_code"], data["discount"], data["bonus_days"], uses)
    if ok:
        d = data["discount"]
        b = data["bonus_days"]
        bonus = []
        if d: bonus.append(f"скидка {d}%")
        if b: bonus.append(f"+{b} дней")
        await message.answer(
            f"✅ <b>Промокод создан!</b>\n\n"
            f"🏷 Код: <code>{data['promo_code']}</code>\n"
            f"🎁 Бонус: {', '.join(bonus) or 'без бонуса'}\n"
            f"🔢 Использований: {uses}",
            reply_markup=admin_back_kb("adm:promos"), parse_mode="HTML"
        )
    else:
        await message.answer("❌ Ошибка — промокод уже существует")
    await state.clear()


@admin_router.callback_query(F.data == "adm:del_promo")
async def admin_del_promo_ask(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(AdminStates.del_promo_id)
    await call.message.edit_text(
        "🗑 Введи ID промокода (смотри в списке промокодов):",
        reply_markup=admin_back_kb("adm:promos")
    )
    await call.answer()


@admin_router.message(AdminStates.del_promo_id)
async def admin_del_promo(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        pid = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введи числовой ID")
        return
    await delete_promo(pid)
    await message.answer(f"✅ Промокод #{pid} удалён", reply_markup=admin_back_kb("adm:promos"))
    await state.clear()


# ═══════════════════════════════════════
#   📢  РАССЫЛКА
# ═══════════════════════════════════════

@admin_router.callback_query(F.data == "adm:broadcast")
async def admin_broadcast_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(AdminStates.broadcast_text)
    users = await get_all_users()
    await call.message.edit_text(
        f"📢 <b>РАССЫЛКА</b>\n\n"
        f"Сообщение получат <b>{len(users)}</b> пользователей.\n\n"
        f"Введи текст рассылки (поддерживается HTML):",
        parse_mode="HTML", reply_markup=admin_back_kb()
    )
    await call.answer()


@admin_router.message(AdminStates.broadcast_text)
async def admin_broadcast_preview(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(broadcast_msg=message.text, broadcast_entities=message.entities)
    await state.set_state(AdminStates.broadcast_ready)
    await message.answer(
        "👁 <b>ПРЕДПРОСМОТР:</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n" +
        message.text +
        "\n\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Подтверди отправку:",
        reply_markup=admin_confirm_broadcast_kb(), parse_mode="HTML"
    )


@admin_router.callback_query(F.data == "adm:broadcast_confirm")
async def admin_broadcast_send(call: CallbackQuery, state: FSMContext, bot: Bot):
    if not is_admin(call.from_user.id):
        return
    data = await state.get_data()
    msg_text = data.get("broadcast_msg", "")
    users = await get_all_users()

    await call.message.edit_text("⏳ Рассылка началась...", parse_mode="HTML")
    await state.clear()

    sent = 0
    failed = 0
    for user in users:
        try:
            await bot.send_message(user["telegram_id"], msg_text, parse_mode="HTML")
            sent += 1
        except Exception:
            failed += 1

    await call.message.edit_text(
        f"✅ <b>Рассылка завершена!</b>\n\n"
        f"📨 Отправлено: <b>{sent}</b>\n"
        f"❌ Не доставлено: <b>{failed}</b>",
        reply_markup=admin_back_kb(), parse_mode="HTML"
    )


# ═══════════════════════════════════════
#   🔔  НАПОМИНАНИЯ ОБ ОПЛАТЕ
# ═══════════════════════════════════════

@admin_router.callback_query(F.data == "adm:remind")
async def admin_remind(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        return
    expiring = await get_expiring_soon(3)
    if not expiring:
        await call.answer("Нет подписок, истекающих в ближайшие 3 дня", show_alert=True)
        return

    sent = 0
    for sub in expiring:
        exp = datetime.fromisoformat(sub["expires_at"])
        days = (exp - datetime.now()).days
        try:
            await bot.send_message(
                sub["user_id"],
                f"⚠️ <b>Напоминание!</b>\n\n"
                f"Ваш VPN истекает через <b>{days} {'день' if days == 1 else 'дня' if days < 5 else 'дней'}</b>.\n\n"
                f"🔄 Продлите подписку, чтобы не потерять доступ!",
                parse_mode="HTML"
            )
            sent += 1
        except Exception:
            pass

    await call.answer(f"✅ Отправлено {sent} напоминаний", show_alert=True)


# ═══════════════════════════════════════
#   ⚙️  НАСТРОЙКИ
# ═══════════════════════════════════════

@admin_router.callback_query(F.data == "adm:settings")
async def admin_settings(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    from config import (XRAY_PANEL_URL, XRAY_INBOUND_ID, VPS_HOST,
                        REFERRAL_BONUS_DAYS, REFERRAL_ENABLED, CHANNEL_USERNAME, SUPPORT_USERNAME)
    text = (
        "⚙️ <b>НАСТРОЙКИ БОТА</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📋 <b>Текущая конфигурация:</b>\n\n"
        f"🌐 VPN Панель: <code>{XRAY_PANEL_URL}</code>\n"
        f"📍 Inbound ID: <code>{XRAY_INBOUND_ID}</code>\n"
        f"🖥 VPS: <code>{VPS_HOST}</code>\n\n"
        f"🎁 Реф. система: {'✅ Вкл' if REFERRAL_ENABLED else '❌ Выкл'}\n"
        f"📅 Бонус реферала: <b>{REFERRAL_BONUS_DAYS} дней</b>\n\n"
        f"📢 Канал: {CHANNEL_USERNAME}\n"
        f"💬 Поддержка: {SUPPORT_USERNAME}\n\n"
        "<i>⚠️ Для изменения настроек отредактируй config.py</i>"
    )
    await call.message.edit_text(text, reply_markup=admin_back_kb(), parse_mode="HTML")
    await call.answer()
