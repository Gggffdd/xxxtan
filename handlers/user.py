import logging
from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import PLANS, ADMIN_IDS, PAYMENT_PROVIDER_TOKEN, REFERRAL_BONUS_DAYS
from database.db import (
    get_user, create_user, get_active_subscription, get_all_subscriptions,
    create_payment, get_promo, use_promo, get_user_referrals
)
from services.subscription_service import activate_subscription, get_subscription_info
from keyboards.keyboards import (
    main_menu_kb, plans_kb, confirm_payment_kb, subscription_kb,
    config_kb, howto_kb, referral_kb, support_kb
)

logger = logging.getLogger(__name__)
router = Router()


class UserStates(StatesGroup):
    waiting_promo = State()


# ═══════════════════════════════════════
#   🚀  СТАРТ / РЕГИСТРАЦИЯ
# ═══════════════════════════════════════

@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot):
    user_id = message.from_user.id
    username = message.from_user.username or ""
    full_name = message.from_user.full_name or ""

    # Обрабатываем реферальную ссылку
    args = message.text.split()
    referrer_id = None
    if len(args) > 1 and args[1].startswith("ref"):
        try:
            referrer_id = int(args[1][3:])
            if referrer_id == user_id:
                referrer_id = None
        except ValueError:
            referrer_id = None

    user = await get_user(user_id)
    if not user:
        await create_user(user_id, username, full_name, referrer_id)
        if referrer_id:
            # Записываем реферала
            import aiosqlite
            from config import DATABASE_PATH
            async with aiosqlite.connect(DATABASE_PATH) as db:
                await db.execute(
                    "INSERT OR IGNORE INTO referrals (referrer_id, referred_id) VALUES (?,?)",
                    (referrer_id, user_id)
                )
                await db.commit()
        is_new = True
    else:
        is_new = False

    if user and user.get("is_banned"):
        await message.answer("⛔ Ваш аккаунт заблокирован. Обратитесь в поддержку.")
        return

    welcome = (
        f"{'🎉 Добро пожаловать' if is_new else '👋 С возвращением'}, "
        f"<b>{full_name}</b>!\n\n"
        f"┌─────────────────────────────┐\n"
        f"│  🛡️  <b>PROTECT VPN</b>              │\n"
        f"│  Быстро · Надёжно · Анонимно │\n"
        f"└─────────────────────────────┘\n\n"
        f"🔒 <i>Шифрование военного уровня</i>\n"
        f"⚡ <i>Скорость до 1 Гбит/с</i>\n"
        f"🌍 <i>Серверы по всему миру</i>\n"
        f"📱 <i>Все устройства</i>\n\n"
        f"Выбери действие 👇"
    )

    if referrer_id and is_new:
        welcome += f"\n\n🎁 <i>Вас пригласил друг — при первой покупке реферер получит +{REFERRAL_BONUS_DAYS} дней!</i>"

    await message.answer(welcome, reply_markup=main_menu_kb(), parse_mode="HTML")


# ═══════════════════════════════════════
#   🛡  ПОКУПКА VPN
# ═══════════════════════════════════════

@router.message(F.text == "🛡 Купить VPN")
@router.callback_query(F.data == "show_plans")
async def show_plans(event: Message | CallbackQuery):
    text = (
        "💎 <b>ВЫБЕРИ ТАРИФ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🥉 <b>1 Месяц</b> — для знакомства\n"
        "🥈 <b>3 Месяца</b> — самый выгодный\n"
        "🥇 <b>1 Год</b> — максимальная экономия\n\n"
        "✅ Без ограничений скорости\n"
        "✅ До 3 устройств одновременно\n"
        "✅ Протокол VLESS Reality (необнаруживаем)\n"
        "✅ Деньги назад в течение 24ч\n"
    )
    kb = plans_kb()
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        await event.answer()
    else:
        await event.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("buy:"))
async def buy_plan(call: CallbackQuery):
    _, plan_key, discount_str = call.data.split(":")
    discount_pct = int(discount_str)
    plan = PLANS.get(plan_key)
    if not plan:
        await call.answer("❌ Тариф не найден", show_alert=True)
        return

    price = plan["price"]
    if discount_pct > 0:
        price = int(price * (1 - discount_pct / 100))

    gb_text = f"{plan['gb']} ГБ" if plan['gb'] > 0 else "Безлимит"
    discount_text = f"\n🏷 <b>Скидка {discount_pct}% применена!</b>" if discount_pct else ""

    text = (
        f"{plan['emoji']} <b>{plan['name'].upper()}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📦 Трафик: <b>{gb_text}</b>\n"
        f"📅 Срок: <b>{plan['days']} дней</b>\n"
        f"📱 Устройств: <b>до 3</b>\n"
        f"🔐 Протокол: <b>VLESS Reality</b>\n\n"
        f"💰 Стоимость: <b>{price} ₽</b>{discount_text}\n\n"
        f"<i>💡 {plan['description']}</i>"
    )

    await call.message.edit_text(
        text,
        reply_markup=confirm_payment_kb(plan_key, price, discount_pct),
        parse_mode="HTML"
    )
    await call.answer()


@router.callback_query(F.data.startswith("pay:"))
async def process_payment(call: CallbackQuery, bot: Bot):
    parts = call.data.split(":")
    plan_key = parts[1]
    price = int(parts[2])
    discount_pct = int(parts[3])

    plan = PLANS.get(plan_key)
    user_id = call.from_user.id

    payment_id = await create_payment(user_id, plan_key, price)

    if PAYMENT_PROVIDER_TOKEN:
        # ── ЮKassa / Stripe / другой провайдер ──
        await bot.send_invoice(
            chat_id=user_id,
            title=f"🛡 VPN — {plan['name']}",
            description=f"Доступ к VPN на {plan['days']} дней. Трафик: {'∞' if plan['gb'] < 0 else plan['gb']} ГБ",
            payload=f"{payment_id}:{plan_key}:{discount_pct}",
            provider_token=PAYMENT_PROVIDER_TOKEN,
            currency="RUB",
            prices=[LabeledPrice(label=plan['name'], amount=price * 100)],
            start_parameter="vpn_buy"
        )
    else:
        # ── Telegram Stars (без токена провайдера) ──
        stars_price = max(1, price // 50)  # примерный курс: 50₽ = 1 звезда
        await bot.send_invoice(
            chat_id=user_id,
            title=f"🛡 VPN — {plan['name']}",
            description=f"VPN на {plan['days']} дней · {'∞' if plan['gb'] < 0 else plan['gb']} ГБ трафика",
            payload=f"{payment_id}:{plan_key}:{discount_pct}",
            currency="XTR",
            prices=[LabeledPrice(label=plan['name'], amount=stars_price)]
        )

    await call.answer("💳 Счёт выставлен!")


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery):
    await query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment(message: Message):
    payment = message.successful_payment
    payload_parts = payment.invoice_payload.split(":")
    payment_id = int(payload_parts[0])
    plan_key = payload_parts[1]
    discount_pct = int(payload_parts[2]) if len(payload_parts) > 2 else 0

    user_id = message.from_user.id
    plan = PLANS[plan_key]

    await message.answer(
        "⏳ <b>Обрабатываем ваш платёж...</b>\n"
        "<i>Создаём VPN конфигурацию, подождите секунду</i>",
        parse_mode="HTML"
    )

    client = await activate_subscription(
        user_id=user_id,
        plan_key=plan_key,
        payment_id=payment_id,
        charge_id=payment.telegram_payment_charge_id
    )

    if client:
        config = client.get("config_link", "")
        text = (
            "✅ <b>ПОДПИСКА АКТИВИРОВАНА!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{plan['emoji']} Тариф: <b>{plan['name']}</b>\n"
            f"📅 Срок: <b>{plan['days']} дней</b>\n\n"
            f"🔑 <b>Ваш VPN-ключ:</b>\n"
            f"<code>{config}</code>\n\n"
            f"📱 <b>Скопируй ключ и вставь в приложение</b>\n"
            f"<i>Нажми «Как подключиться?» для инструкции</i>"
        )
        await message.answer(text, reply_markup=config_kb(config), parse_mode="HTML")
    else:
        await message.answer(
            "⚠️ <b>Оплата прошла, но возникла техническая ошибка.</b>\n\n"
            "Не волнуйтесь — деньги зачислены. Мы свяжемся с вами в течение 1 часа.\n"
            "Или напишите в поддержку с этим номером платежа: "
            f"<code>{payment_id}</code>",
            reply_markup=support_kb(),
            parse_mode="HTML"
        )


# ═══════════════════════════════════════
#   📊  МОЯ ПОДПИСКА
# ═══════════════════════════════════════

@router.message(F.text == "📊 Моя подписка")
@router.callback_query(F.data == "my_sub")
async def my_subscription(event: Message | CallbackQuery):
    user_id = event.from_user.id
    info = await get_subscription_info(user_id)

    if not info:
        text = (
            "📭 <b>У вас нет активной подписки</b>\n\n"
            "🛡 Защитите своё соединение прямо сейчас!\n"
            "Нажмите кнопку ниже, чтобы выбрать тариф."
        )
    else:
        expires = datetime.fromisoformat(info["expires_at"])
        days_left = info["days_left"]
        status_emoji = "✅" if days_left > 3 else "⚠️" if days_left > 0 else "❌"
        stats = info.get("stats")
        traffic_text = ""
        if stats:
            used = stats.get("used_gb", 0)
            total = stats.get("total_gb", -1)
            if total > 0:
                pct = min(100, int(used / total * 100))
                bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
                traffic_text = f"\n\n📶 <b>Трафик:</b>\n[{bar}] {pct}%\n<i>{used} ГБ из {total} ГБ использовано</i>"
            else:
                traffic_text = f"\n\n📶 <b>Использовано:</b> {used} ГБ (безлимит)"

        text = (
            f"🛡️ <b>ВАША ПОДПИСКА</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{PLANS[info['plan_key']]['emoji']} Тариф: <b>{PLANS[info['plan_key']]['name']}</b>\n"
            f"{status_emoji} Статус: <b>{'Активна' if days_left > 0 else 'Истекла'}</b>\n"
            f"📅 Истекает: <b>{expires.strftime('%d.%m.%Y')}</b>\n"
            f"⏳ Осталось: <b>{days_left} дн.</b>"
            f"{traffic_text}"
        )

    kb = subscription_kb(info is not None)
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        await event.answer()
    else:
        await event.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "my_config")
async def my_config(call: CallbackQuery):
    info = await get_subscription_info(call.from_user.id)
    if not info:
        await call.answer("❌ Нет активной подписки", show_alert=True)
        return

    config = info.get("config_link", "Конфиг недоступен")
    text = (
        "🔑 <b>ВАШ VPN-КЛЮЧ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<code>{config}</code>\n\n"
        "📋 <i>Нажми на ключ, чтобы скопировать</i>\n"
        "📱 <i>Или используй кнопки ниже для открытия в приложении</i>"
    )
    await call.message.edit_text(text, reply_markup=config_kb(config), parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data == "howto")
async def howto(call: CallbackQuery):
    text = (
        "📱 <b>КАК ПОДКЛЮЧИТЬСЯ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "1️⃣ Скачай приложение под своё устройство\n"
        "2️⃣ Нажми <b>«Добавить конфигурацию»</b>\n"
        "3️⃣ Вставь свой VPN-ключ\n"
        "4️⃣ Нажми <b>«Подключить»</b> ✅\n\n"
        "📲 <b>Рекомендуемые приложения:</b>"
    )
    await call.message.edit_text(text, reply_markup=howto_kb(), parse_mode="HTML")
    await call.answer()


# ═══════════════════════════════════════
#   🎁  РЕФЕРАЛЫ
# ═══════════════════════════════════════

@router.message(F.text == "🎁 Рефералы")
async def referrals(message: Message, bot: Bot):
    user_id = message.from_user.id
    bot_info = await bot.get_me()
    refs = await get_user_referrals(user_id)

    ref_link = f"https://t.me/{bot_info.username}?start=ref{user_id}"

    text = (
        "🎁 <b>РЕФЕРАЛЬНАЯ ПРОГРАММА</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 Ваших рефералов: <b>{len(refs)}</b>\n\n"
        "💡 <b>Как это работает:</b>\n"
        f"• Поделись своей ссылкой с другом\n"
        f"• Друг регистрируется и покупает VPN\n"
        f"• Ты получаешь <b>+{REFERRAL_BONUS_DAYS} дней</b> к подписке!\n\n"
        f"🔗 <b>Твоя реферальная ссылка:</b>\n"
        f"<code>{ref_link}</code>"
    )

    if refs:
        text += "\n\n👥 <b>Твои рефералы:</b>\n"
        for i, ref in enumerate(refs[:5], 1):
            name = ref.get("full_name") or ref.get("username") or "Пользователь"
            bonus = "✅" if ref.get("bonus_given") else "⏳"
            text += f"{i}. {name} {bonus}\n"
        if len(refs) > 5:
            text += f"<i>...и ещё {len(refs) - 5}</i>"

    await message.answer(text, reply_markup=referral_kb(bot_info.username, user_id), parse_mode="HTML")


# ═══════════════════════════════════════
#   🏷  ПРОМОКОД
# ═══════════════════════════════════════

@router.message(F.text == "🏷 Промокод")
async def ask_promo(message: Message, state: FSMContext):
    await state.set_state(UserStates.waiting_promo)
    await message.answer(
        "🏷 <b>ВВЕДИТЕ ПРОМОКОД</b>\n\n"
        "Отправьте промокод в следующем сообщении.\n"
        "Например: <code>SUMMER25</code>",
        parse_mode="HTML"
    )


@router.message(UserStates.waiting_promo)
async def check_promo(message: Message, state: FSMContext):
    code = message.text.strip().upper()
    promo = await get_promo(code)

    if not promo:
        await message.answer(
            "❌ <b>Промокод не найден или уже использован</b>\n\n"
            "<i>Проверьте правильность написания</i>",
            parse_mode="HTML"
        )
        await state.clear()
        return

    await state.clear()

    # Проверяем — не использовал ли уже
    import aiosqlite
    from config import DATABASE_PATH
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            "SELECT id FROM promo_uses WHERE user_id = ? AND promo_id = ?",
            (message.from_user.id, promo["id"])
        ) as cur:
            already_used = await cur.fetchone()

    if already_used:
        await message.answer("❌ Вы уже использовали этот промокод.")
        return

    await use_promo(message.from_user.id, promo["id"])

    bonus_text = []
    if promo["discount_pct"]:
        bonus_text.append(f"🏷 Скидка <b>{promo['discount_pct']}%</b>")
    if promo["bonus_days"]:
        bonus_text.append(f"📅 +<b>{promo['bonus_days']} дней</b> к подписке")

    await message.answer(
        f"✅ <b>Промокод активирован!</b>\n\n"
        f"🎁 Вы получили:\n" + "\n".join(bonus_text) + "\n\n"
        f"<i>Скидка применится при следующей покупке</i>",
        reply_markup=plans_kb(promo["discount_pct"]),
        parse_mode="HTML"
    )


# ═══════════════════════════════════════
#   📖  ИНСТРУКЦИЯ / ПОДДЕРЖКА
# ═══════════════════════════════════════

@router.message(F.text == "📖 Инструкция")
async def instruction(message: Message):
    await message.answer(
        "📖 <b>ИНСТРУКЦИЯ ПО ПОДКЛЮЧЕНИЮ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🤖 <b>Android</b>\n"
        "1. Установи V2rayNG из Google Play\n"
        "2. Нажми «+» → «Импорт из буфера обмена»\n"
        "3. Вставь свой ключ → подключайся!\n\n"
        "🍎 <b>iPhone / iPad</b>\n"
        "1. Установи Streisand из App Store\n"
        "2. Нажми «+» → «Вставить из буфера»\n"
        "3. Вставь ключ → включай!\n\n"
        "💻 <b>Windows</b>\n"
        "1. Скачай V2rayN с GitHub\n"
        "2. Серверы → «Добавить VLESS»\n"
        "3. Вставь ключ → ОК → подключайся!\n\n"
        "🍏 <b>macOS</b>\n"
        "1. Установи V2rayU\n"
        "2. Configure → Paste link → Connect\n\n"
        "❓ <b>Проблемы?</b> Напишите в поддержку 👇",
        reply_markup=support_kb(),
        parse_mode="HTML"
    )


@router.message(F.text == "💬 Поддержка")
async def support(message: Message):
    await message.answer(
        "💬 <b>ПОДДЕРЖКА</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Мы работаем <b>7 дней в неделю</b>\n"
        "Время ответа: до <b>2 часов</b>\n\n"
        "📌 При обращении укажите:\n"
        "• Ваш Telegram ID\n"
        "• Описание проблемы\n"
        "• Ваше устройство (iOS/Android/ПК)\n\n"
        "🔹 Частые вопросы:\n"
        "❓ <i>VPN не подключается</i> — проверь, что ключ скопирован полностью\n"
        "❓ <i>Маленькая скорость</i> — переподключись к серверу\n"
        "❓ <i>Хочу вернуть деньги</i> — возврат в течение 24ч",
        reply_markup=support_kb(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "cancel")
async def cancel(call: CallbackQuery):
    await call.message.delete()
    await call.answer()
