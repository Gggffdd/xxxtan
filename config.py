# ════════════════════════════════════════
#   ⚙️  КОНФИГ — НАСТРОЙ ЭТИ ПАРАМЕТРЫ
# ════════════════════════════════════════

# 🤖 Telegram
BOT_TOKEN = "8830598393:AAED3deZyNn9yXRma6AQ36KFrJnmVh7VNzk"
ADMIN_IDS = [1043757036]  # Список ID администраторов

# 💳 Оплата (Telegram Stars или ЮKassa)
PAYMENT_PROVIDER_TOKEN = ""  # Оставь пустым для Telegram Stars
                              # Или вставь токен ЮKassa/Stripe

# 🖥️ 3x-ui VPN Панель (https://github.com/MHSanaei/3x-ui)
# Установи 3x-ui на свой VPS и укажи данные:
XRAY_PANEL_URL    = "http://YOUR_VPS_IP:54321"   # URL панели 3x-ui
XRAY_PANEL_USER   = "admin"                       # Логин панели
XRAY_PANEL_PASS   = "admin"                       # Пароль панели
XRAY_INBOUND_ID   = 1                             # ID inbound (смотри в панели)

# 🌐 Твой VPS (для показа пользователям)
VPS_HOST = "YOUR_VPS_IP"   # IP или домен твоего сервера

# 📦 База данных
DATABASE_PATH = "vpn_bot.db"

# 💰 Цены на тарифы (в рублях)
PLANS = {
    "1month": {
        "name": "🗓 1 Месяц",
        "price": 149,
        "days": 30,
        "gb": 100,
        "emoji": "🥉",
        "description": "Идеально для старта"
    },
    "3months": {
        "name": "📅 3 Месяца",
        "price": 399,
        "days": 90,
        "gb": 300,
        "emoji": "🥈",
        "description": "Самый популярный"
    },
    "1year": {
        "name": "🗓️ 1 Год",
        "price": 1299,
        "days": 365,
        "gb": -1,           # -1 = безлимит
        "emoji": "🥇",
        "description": "Максимальная выгода"
    }
}

# 📢 Канал для проверки подписки (опционально)
CHANNEL_ID = None           # Например: "@my_channel" или None

# 🔗 Ссылки
SUPPORT_USERNAME = "@your_support"
CHANNEL_USERNAME = "@your_channel"

# 🎁 Реферальная система
REFERRAL_BONUS_DAYS = 7     # Дней за каждого реферала
REFERRAL_ENABLED = True
