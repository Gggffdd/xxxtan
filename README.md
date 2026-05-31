# 🛡 VPN BOT — Полное руководство по запуску

## 📁 Структура проекта
```
vpn_bot/
├── bot.py                    # 🚀 Точка входа
├── config.py                 # ⚙️ ВСЕ НАСТРОЙКИ ЗДЕСЬ
├── requirements.txt          # 📦 Зависимости
├── database/
│   └── db.py                 # 🗄 База данных SQLite
├── handlers/
│   ├── user.py               # 👤 Команды пользователей
│   └── admin.py              # 👑 Админ панель
├── services/
│   ├── xray_service.py       # 🖥 Интеграция с 3x-ui VPN
│   └── subscription_service.py # 🛡 Управление подписками
├── keyboards/
│   └── keyboards.py          # ⌨️ Все кнопки
├── middlewares/
│   └── __init__.py           # 🔒 Проверка банов
└── utils/
    └── scheduler.py          # ⏰ Автозадачи
```

---

## 🚀 БЫСТРЫЙ СТАРТ

### Шаг 1 — Арендуй VPS
Рекомендую: **Hetzner**, **Aeza**, **Serverspace** (от 200 ₽/мес)
Нужно: Ubuntu 22.04, 1 CPU, 1GB RAM

### Шаг 2 — Установи 3x-ui на VPS
```bash
bash <(curl -Ls https://raw.githubusercontent.com/mhsanaei/3x-ui/master/install.sh)
```
После установки панель будет на `http://IP_СЕРВЕРА:54321`
Логин/пароль по умолчанию: `admin` / `admin`

### Шаг 3 — Настрой 3x-ui
1. Открой `http://IP:54321` в браузере
2. Войди и смени пароль
3. Зайди в **Inbounds** → **Add Inbound**
4. Выбери протокол: `VLESS` + `Reality` (рекомендуется)
5. Запомни **ID** созданного inbound (обычно 1)

### Шаг 4 — Настрой config.py
```python
XRAY_PANEL_URL  = "http://ВАШ_IP:54321"
XRAY_PANEL_USER = "admin"
XRAY_PANEL_PASS = "ваш_пароль"
XRAY_INBOUND_ID = 1          # ID из панели
VPS_HOST        = "ВАШ_IP"

SUPPORT_USERNAME = "@ваш_юзернейм"
CHANNEL_USERNAME = "@ваш_канал"
```

### Шаг 5 — Запуск бота
```bash
cd vpn_bot
pip install -r requirements.txt
python bot.py
```

### Шаг 6 — Автозапуск (systemd)
```bash
sudo nano /etc/systemd/system/vpnbot.service
```
```ini
[Unit]
Description=VPN Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/vpn_bot
ExecStart=/usr/bin/python3 /root/vpn_bot/bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl daemon-reload
sudo systemctl enable vpnbot
sudo systemctl start vpnbot
sudo systemctl status vpnbot
```

---

## 💳 НАСТРОЙКА ОПЛАТЫ

### Вариант A: Telegram Stars (проще, без документов)
- Оставь `PAYMENT_PROVIDER_TOKEN = ""`
- Пользователи платят звёздами Telegram
- Деньги приходят на баланс бота

### Вариант B: ЮKassa (рубли, нужно ИП/ООО)
1. Зарегистрируйся на kassa.yandex.ru
2. В @BotFather → Payments → ЮKassa
3. Вставь токен в `PAYMENT_PROVIDER_TOKEN`

### Вариант C: Cryptomus (криптовалюта, без документов)
- Используй Cryptomus API + Webhook
- Требует доработки кода (напиши в поддержку)

---

## 👑 КОМАНДЫ АДМИНА

| Команда | Действие |
|---------|----------|
| `/admin` | Открыть панель |
| Статистика | Все показатели |
| Пользователи | Поиск, бан, выдача VPN |
| Промокоды | Создание/удаление |
| Рассылка | Сообщение всем |
| Напомнить об оплате | Тем, у кого скоро конец |
| VPN Панель | Статус 3x-ui |

---

## 🔧 ВОЗМОЖНЫЕ ПРОБЛЕМЫ

**Бот не создаёт клиентов в VPN:**
- Проверь доступность `XRAY_PANEL_URL`
- Убедись, что логин/пароль верные
- Проверь, что INBOUND_ID существует в панели

**Ошибка при оплате:**
- Для Stars: убедись, что токен провайдера пустой
- Для ЮKassa: токен должен быть `TEST` или `LIVE`

**Подписка создана, но ключ не работает:**
- Проверь тип протокола в 3x-ui (должен быть VLESS Reality)
- Убедись, что `VPS_HOST` — IP или домен без http://

---

## 📞 Если что-то не работает
Напиши в Telegram: @your_support
