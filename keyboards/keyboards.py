from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from config import PLANS, SUPPORT_USERNAME, CHANNEL_USERNAME


# ═══════════════════════════════════════
#   👤  ПОЛЬЗОВАТЕЛЬСКИЕ КЛАВИАТУРЫ
# ═══════════════════════════════════════

def main_menu_kb() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.row(
        KeyboardButton(text="🛡 Купить VPN"),
        KeyboardButton(text="📊 Моя подписка")
    )
    kb.row(
        KeyboardButton(text="🎁 Рефералы"),
        KeyboardButton(text="🏷 Промокод")
    )
    kb.row(
        KeyboardButton(text="📖 Инструкция"),
        KeyboardButton(text="💬 Поддержка")
    )
    return kb.as_markup(resize_keyboard=True)


def plans_kb(discount_pct: int = 0) -> InlineKeyboardMarkup:
    """Клавиатура выбора тарифа"""
    builder = InlineKeyboardBuilder()
    for key, plan in PLANS.items():
        price = plan["price"]
        if discount_pct > 0:
            price = int(price * (1 - discount_pct / 100))
        gb_text = f"{plan['gb']} ГБ" if plan['gb'] > 0 else "∞ ГБ"
        builder.row(InlineKeyboardButton(
            text=f"{plan['emoji']} {plan['name']} — {price}₽ / {gb_text}",
            callback_data=f"buy:{key}:{discount_pct}"
        ))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"))
    return builder.as_markup()


def confirm_payment_kb(plan_key: str, price: int, discount_pct: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text=f"💳 Оплатить {price}₽",
        callback_data=f"pay:{plan_key}:{price}:{discount_pct}"
    ))
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="show_plans"))
    return builder.as_markup()


def subscription_kb(has_sub: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if has_sub:
        builder.row(InlineKeyboardButton(text="🔑 Мой конфиг", callback_data="my_config"))
        builder.row(InlineKeyboardButton(text="🔄 Продлить", callback_data="show_plans"))
        builder.row(InlineKeyboardButton(
            text="📱 Как подключиться?", callback_data="howto")
        )
    else:
        builder.row(InlineKeyboardButton(text="🛡 Купить VPN", callback_data="show_plans"))
    return builder.as_markup()


def config_kb(config_link: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="📋 Скопировать ключ", callback_data="copy_config"
    ))
    builder.row(InlineKeyboardButton(
        text="📱 Открыть в V2rayNG", url=f"v2rayng://install-config?url={config_link}"
    ))
    builder.row(InlineKeyboardButton(
        text="📱 Открыть в Streisand", url=f"streisand://import/{config_link}"
    ))
    builder.row(InlineKeyboardButton(text="💬 Поддержка", url=f"https://t.me/{SUPPORT_USERNAME.lstrip('@')}"))
    return builder.as_markup()


def howto_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="🤖 Android — V2rayNG",
        url="https://play.google.com/store/apps/details?id=com.v2ray.ang"
    ))
    builder.row(InlineKeyboardButton(
        text="🍎 iOS — Streisand",
        url="https://apps.apple.com/app/streisand/id6450534064"
    ))
    builder.row(InlineKeyboardButton(
        text="💻 Windows — V2rayN",
        url="https://github.com/2dust/v2rayN/releases"
    ))
    builder.row(InlineKeyboardButton(
        text="🍏 macOS — V2rayU",
        url="https://github.com/yanue/V2rayU/releases"
    ))
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="my_sub"))
    return builder.as_markup()


def referral_kb(bot_username: str, user_id: int) -> InlineKeyboardMarkup:
    ref_link = f"https://t.me/{bot_username}?start=ref{user_id}"
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="📤 Поделиться ссылкой",
        url=f"https://t.me/share/url?url={ref_link}&text=🛡 Попробуй лучший VPN!"
    ))
    return builder.as_markup()


def support_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="💬 Написать в поддержку",
        url=f"https://t.me/{SUPPORT_USERNAME.lstrip('@')}"
    ))
    if CHANNEL_USERNAME:
        builder.row(InlineKeyboardButton(
            text="📢 Наш канал",
            url=f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}"
        ))
    return builder.as_markup()


# ═══════════════════════════════════════
#   👑  АДМИНСКИЕ КЛАВИАТУРЫ
# ═══════════════════════════════════════

def admin_main_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📊 Статистика", callback_data="adm:stats"),
        InlineKeyboardButton(text="👥 Пользователи", callback_data="adm:users")
    )
    builder.row(
        InlineKeyboardButton(text="🏷 Промокоды", callback_data="adm:promos"),
        InlineKeyboardButton(text="📢 Рассылка", callback_data="adm:broadcast")
    )
    builder.row(
        InlineKeyboardButton(text="⚙️ VPN Панель", callback_data="adm:vpn_status"),
        InlineKeyboardButton(text="💰 Финансы", callback_data="adm:finance")
    )
    builder.row(
        InlineKeyboardButton(text="🔔 Напомнить об оплате", callback_data="adm:remind"),
        InlineKeyboardButton(text="⚙️ Настройки", callback_data="adm:settings")
    )
    return builder.as_markup()


def admin_users_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔍 Найти пользователя", callback_data="adm:find_user"))
    builder.row(
        InlineKeyboardButton(text="⛔ Забанить", callback_data="adm:ban_user"),
        InlineKeyboardButton(text="✅ Разбанить", callback_data="adm:unban_user")
    )
    builder.row(InlineKeyboardButton(text="🎁 Выдать подписку", callback_data="adm:give_sub"))
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="adm:main"))
    return builder.as_markup()


def admin_promos_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Создать промокод", callback_data="adm:create_promo"))
    builder.row(InlineKeyboardButton(text="📋 Список промокодов", callback_data="adm:list_promos"))
    builder.row(InlineKeyboardButton(text="🗑 Удалить промокод", callback_data="adm:del_promo"))
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="adm:main"))
    return builder.as_markup()


def admin_back_kb(back_cb: str = "adm:main") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data=back_cb))
    return builder.as_markup()


def admin_confirm_broadcast_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Отправить всем", callback_data="adm:broadcast_confirm"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="adm:main")
    )
    return builder.as_markup()


def admin_give_sub_plans_kb(user_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for key, plan in PLANS.items():
        builder.row(InlineKeyboardButton(
            text=f"{plan['emoji']} {plan['name']}",
            callback_data=f"adm:give:{user_id}:{key}"
        ))
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="adm:users"))
    return builder.as_markup()


def admin_user_actions_kb(user_id: int, is_banned: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if is_banned:
        builder.row(InlineKeyboardButton(text="✅ Разбанить", callback_data=f"adm:unban:{user_id}"))
    else:
        builder.row(InlineKeyboardButton(text="⛔ Забанить", callback_data=f"adm:ban:{user_id}"))
    builder.row(InlineKeyboardButton(text="🎁 Выдать подписку", callback_data=f"adm:give_to:{user_id}"))
    builder.row(InlineKeyboardButton(text="🔑 Сбросить трафик", callback_data=f"adm:reset_traffic:{user_id}"))
    builder.row(InlineKeyboardButton(text="📩 Написать", callback_data=f"adm:msg:{user_id}"))
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="adm:users"))
    return builder.as_markup()
