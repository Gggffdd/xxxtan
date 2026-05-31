import aiosqlite
import logging
from datetime import datetime, timedelta
from config import DATABASE_PATH

logger = logging.getLogger(__name__)


async def init_db():
    """Инициализация базы данных"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id              INTEGER PRIMARY KEY,
                telegram_id     INTEGER UNIQUE NOT NULL,
                username        TEXT,
                full_name       TEXT,
                referrer_id     INTEGER,
                balance         INTEGER DEFAULT 0,
                is_banned       INTEGER DEFAULT 0,
                created_at      TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS subscriptions (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER NOT NULL,
                plan_key        TEXT NOT NULL,
                xray_client_id  TEXT,
                xray_email      TEXT UNIQUE,
                config_link     TEXT,
                status          TEXT DEFAULT 'active',
                started_at      TEXT,
                expires_at      TEXT,
                gb_limit        INTEGER DEFAULT -1,
                created_at      TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(telegram_id)
            );

            CREATE TABLE IF NOT EXISTS payments (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER NOT NULL,
                plan_key        TEXT NOT NULL,
                amount          INTEGER NOT NULL,
                method          TEXT DEFAULT 'stars',
                status          TEXT DEFAULT 'pending',
                telegram_charge_id TEXT,
                created_at      TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(telegram_id)
            );

            CREATE TABLE IF NOT EXISTS promo_codes (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                code            TEXT UNIQUE NOT NULL,
                discount_pct    INTEGER DEFAULT 0,
                bonus_days      INTEGER DEFAULT 0,
                uses_left       INTEGER DEFAULT 1,
                expires_at      TEXT,
                created_at      TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS promo_uses (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER NOT NULL,
                promo_id        INTEGER NOT NULL,
                used_at         TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, promo_id)
            );

            CREATE TABLE IF NOT EXISTS broadcast_log (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id        INTEGER,
                message         TEXT,
                sent_count      INTEGER DEFAULT 0,
                created_at      TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS referrals (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id     INTEGER NOT NULL,
                referred_id     INTEGER NOT NULL UNIQUE,
                bonus_given     INTEGER DEFAULT 0,
                created_at      TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        await db.commit()
    logger.info("✅ База данных инициализирована")


# ──────────────── ПОЛЬЗОВАТЕЛИ ────────────────

async def get_user(telegram_id: int) -> dict | None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def create_user(telegram_id: int, username: str, full_name: str, referrer_id: int = None):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (telegram_id, username, full_name, referrer_id) VALUES (?,?,?,?)",
            (telegram_id, username, full_name, referrer_id)
        )
        await db.commit()


async def get_all_users() -> list[dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE is_banned = 0") as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_users_count() -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cur:
            return (await cur.fetchone())[0]


async def ban_user(telegram_id: int, ban: bool = True):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE users SET is_banned = ? WHERE telegram_id = ?",
            (1 if ban else 0, telegram_id)
        )
        await db.commit()


async def add_balance(telegram_id: int, amount: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE users SET balance = balance + ? WHERE telegram_id = ?",
            (amount, telegram_id)
        )
        await db.commit()


async def get_user_referrals(telegram_id: int) -> list[dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT r.*, u.username, u.full_name FROM referrals r "
            "JOIN users u ON r.referred_id = u.telegram_id "
            "WHERE r.referrer_id = ?", (telegram_id,)
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


# ──────────────── ПОДПИСКИ ────────────────

async def get_active_subscription(user_id: int) -> dict | None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM subscriptions WHERE user_id = ? AND status = 'active' ORDER BY expires_at DESC LIMIT 1",
            (user_id,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def get_all_subscriptions(user_id: int) -> list[dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM subscriptions WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,)
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def create_subscription(user_id: int, plan_key: str, xray_client_id: str,
                               xray_email: str, config_link: str, days: int, gb: int):
    started = datetime.now()
    expires = started + timedelta(days=days)
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """INSERT INTO subscriptions
               (user_id, plan_key, xray_client_id, xray_email, config_link, status, started_at, expires_at, gb_limit)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (user_id, plan_key, xray_client_id, xray_email, config_link,
             'active', started.isoformat(), expires.isoformat(), gb)
        )
        await db.commit()


async def extend_subscription(sub_id: int, days: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("SELECT expires_at FROM subscriptions WHERE id = ?", (sub_id,)) as cur:
            row = await cur.fetchone()
        if row:
            current = datetime.fromisoformat(row[0])
            new_expires = max(current, datetime.now()) + timedelta(days=days)
            await db.execute(
                "UPDATE subscriptions SET expires_at = ? WHERE id = ?",
                (new_expires.isoformat(), sub_id)
            )
            await db.commit()


async def deactivate_subscription(sub_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE subscriptions SET status = 'expired' WHERE id = ?", (sub_id,))
        await db.commit()


async def get_active_subs_count() -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        now = datetime.now().isoformat()
        async with db.execute(
            "SELECT COUNT(*) FROM subscriptions WHERE status = 'active' AND expires_at > ?", (now,)
        ) as cur:
            return (await cur.fetchone())[0]


async def get_expiring_soon(days: int = 3) -> list[dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        now = datetime.now()
        soon = (now + timedelta(days=days)).isoformat()
        async with db.execute(
            "SELECT * FROM subscriptions WHERE status = 'active' AND expires_at <= ? AND expires_at > ?",
            (soon, now.isoformat())
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


# ──────────────── ПЛАТЕЖИ ────────────────

async def create_payment(user_id: int, plan_key: str, amount: int, method: str = 'stars') -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cur = await db.execute(
            "INSERT INTO payments (user_id, plan_key, amount, method) VALUES (?,?,?,?)",
            (user_id, plan_key, amount, method)
        )
        await db.commit()
        return cur.lastrowid


async def confirm_payment(payment_id: int, charge_id: str = None):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE payments SET status = 'paid', telegram_charge_id = ? WHERE id = ?",
            (charge_id, payment_id)
        )
        await db.commit()


async def get_total_revenue() -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("SELECT SUM(amount) FROM payments WHERE status = 'paid'") as cur:
            result = (await cur.fetchone())[0]
            return result or 0


async def get_today_revenue() -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        today = datetime.now().strftime("%Y-%m-%d")
        async with db.execute(
            "SELECT SUM(amount) FROM payments WHERE status = 'paid' AND created_at LIKE ?",
            (f"{today}%",)
        ) as cur:
            result = (await cur.fetchone())[0]
            return result or 0


# ──────────────── ПРОМОКОДЫ ────────────────

async def get_promo(code: str) -> dict | None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM promo_codes WHERE code = ? AND uses_left > 0", (code.upper(),)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def use_promo(user_id: int, promo_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO promo_uses (user_id, promo_id) VALUES (?,?)",
            (user_id, promo_id)
        )
        await db.execute(
            "UPDATE promo_codes SET uses_left = uses_left - 1 WHERE id = ?", (promo_id,)
        )
        await db.commit()


async def create_promo(code: str, discount_pct: int, bonus_days: int, uses: int, expires_at: str = None) -> bool:
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute(
                "INSERT INTO promo_codes (code, discount_pct, bonus_days, uses_left, expires_at) VALUES (?,?,?,?,?)",
                (code.upper(), discount_pct, bonus_days, uses, expires_at)
            )
            await db.commit()
            return True
    except Exception:
        return False


async def get_all_promos() -> list[dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM promo_codes ORDER BY created_at DESC") as cur:
            return [dict(r) for r in await cur.fetchall()]


async def delete_promo(promo_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM promo_codes WHERE id = ?", (promo_id,))
        await db.commit()


# ──────────────── СТАТИСТИКА ────────────────

async def get_stats() -> dict:
    return {
        "users": await get_users_count(),
        "active_subs": await get_active_subs_count(),
        "total_revenue": await get_total_revenue(),
        "today_revenue": await get_today_revenue(),
    }
