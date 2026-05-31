"""
╔══════════════════════════════════════════════════════╗
║  🖥️  СЕРВИС ИНТЕГРАЦИИ С 3x-ui VPN ПАНЕЛЬЮ           ║
║                                                      ║
║  3x-ui — бесплатная панель для VPN на базе Xray      ║
║  GitHub: https://github.com/MHSanaei/3x-ui           ║
║                                                      ║
║  КАК УСТАНОВИТЬ 3x-ui НА VPS:                        ║
║  bash <(curl -Ls https://raw.githubusercontent.com/  ║
║  mhsanaei/3x-ui/master/install.sh)                   ║
╚══════════════════════════════════════════════════════╝
"""

import aiohttp
import uuid
import logging
from datetime import datetime, timedelta
from config import XRAY_PANEL_URL, XRAY_PANEL_USER, XRAY_PANEL_PASS, XRAY_INBOUND_ID, VPS_HOST

logger = logging.getLogger(__name__)


class XrayPanelService:
    """Сервис для работы с 3x-ui панелью через её API"""

    def __init__(self):
        self.base_url = XRAY_PANEL_URL.rstrip("/")
        self.session: aiohttp.ClientSession | None = None
        self.cookie = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if not self.session or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    async def login(self) -> bool:
        """Авторизация в 3x-ui панели"""
        try:
            sess = await self._get_session()
            async with sess.post(
                f"{self.base_url}/login",
                data={"username": XRAY_PANEL_USER, "password": XRAY_PANEL_PASS},
                ssl=False
            ) as resp:
                if resp.status == 200:
                    self.cookie = resp.cookies
                    logger.info("✅ Авторизация в 3x-ui успешна")
                    return True
                logger.error(f"❌ Ошибка авторизации 3x-ui: {resp.status}")
                return False
        except Exception as e:
            logger.error(f"❌ Не удалось подключиться к 3x-ui: {e}")
            return False

    async def add_client(self, user_id: int, days: int, gb_limit: int) -> dict | None:
        """
        Создаёт нового VPN клиента в 3x-ui.
        Возвращает словарь с client_id, email, и ссылкой на конфиг.
        """
        if not await self.login():
            return None

        client_id = str(uuid.uuid4())
        email = f"user_{user_id}_{int(datetime.now().timestamp())}"
        expire_ms = int((datetime.now() + timedelta(days=days)).timestamp() * 1000)
        total_bytes = gb_limit * 1024**3 if gb_limit > 0 else 0  # 0 = безлимит

        payload = {
            "id": XRAY_INBOUND_ID,
            "settings": f'{{"clients": [{{"id": "{client_id}", "email": "{email}", '
                        f'"limitIp": 3, "totalGB": {total_bytes}, '
                        f'"expiryTime": {expire_ms}, "enable": true, '
                        f'"tgId": "", "subId": ""}}]}}'
        }

        try:
            sess = await self._get_session()
            async with sess.post(
                f"{self.base_url}/panel/api/inbounds/addClient",
                json=payload,
                cookies=self.cookie,
                ssl=False
            ) as resp:
                data = await resp.json()
                if data.get("success"):
                    config_link = await self._get_client_link(client_id, email)
                    logger.info(f"✅ Клиент {email} создан в 3x-ui")
                    return {
                        "client_id": client_id,
                        "email": email,
                        "config_link": config_link
                    }
                logger.error(f"❌ Ошибка создания клиента: {data}")
                return None
        except Exception as e:
            logger.error(f"❌ Ошибка API 3x-ui: {e}")
            return None

    async def _get_client_link(self, client_id: str, email: str) -> str:
        """
        Формирует ссылку подключения для клиента.
        Формат зависит от типа inbound (VLESS, VMess, Trojan и т.д.)
        Здесь пример для VLESS + Reality (самый современный протокол)
        """
        try:
            sess = await self._get_session()
            async with sess.get(
                f"{self.base_url}/panel/api/inbounds/get/{XRAY_INBOUND_ID}",
                cookies=self.cookie,
                ssl=False
            ) as resp:
                data = await resp.json()
                if data.get("success"):
                    obj = data["obj"]
                    protocol = obj.get("protocol", "vless")
                    port = obj.get("port", 443)
                    # Парсим stream settings для Reality
                    import json
                    stream = json.loads(obj.get("streamSettings", "{}"))
                    security = stream.get("security", "reality")
                    reality = stream.get("realitySettings", {})
                    public_key = reality.get("publicKey", "")
                    server_name = reality.get("serverNames", ["google.com"])[0]
                    short_id = reality.get("shortIds", [""])[0]
                    fp = reality.get("fingerprint", "chrome")

                    if protocol == "vless" and security == "reality":
                        link = (f"vless://{client_id}@{VPS_HOST}:{port}"
                                f"?type=tcp&security=reality"
                                f"&pbk={public_key}"
                                f"&fp={fp}"
                                f"&sni={server_name}"
                                f"&sid={short_id}"
                                f"&spx=%2F#{email}")
                        return link
        except Exception as e:
            logger.error(f"Ошибка получения ссылки: {e}")

        # Fallback — общая ссылка на subscription
        return f"{self.base_url}/sub/{client_id}"

    async def remove_client(self, xray_email: str) -> bool:
        """Удаляет клиента из 3x-ui"""
        if not await self.login():
            return False
        try:
            sess = await self._get_session()
            async with sess.post(
                f"{self.base_url}/panel/api/inbounds/{XRAY_INBOUND_ID}/delClient/{xray_email}",
                cookies=self.cookie,
                ssl=False
            ) as resp:
                data = await resp.json()
                return data.get("success", False)
        except Exception as e:
            logger.error(f"Ошибка удаления клиента: {e}")
            return False

    async def reset_client_traffic(self, xray_email: str) -> bool:
        """Сбрасывает трафик клиента"""
        if not await self.login():
            return False
        try:
            sess = await self._get_session()
            async with sess.post(
                f"{self.base_url}/panel/api/inbounds/{XRAY_INBOUND_ID}/resetClientTraffic/{xray_email}",
                cookies=self.cookie,
                ssl=False
            ) as resp:
                data = await resp.json()
                return data.get("success", False)
        except Exception as e:
            logger.error(f"Ошибка сброса трафика: {e}")
            return False

    async def get_client_stats(self, xray_email: str) -> dict | None:
        """Получает статистику клиента (трафик)"""
        if not await self.login():
            return None
        try:
            sess = await self._get_session()
            async with sess.get(
                f"{self.base_url}/panel/api/inbounds/getClientTraffics/{xray_email}",
                cookies=self.cookie,
                ssl=False
            ) as resp:
                data = await resp.json()
                if data.get("success") and data.get("obj"):
                    obj = data["obj"]
                    used_bytes = obj.get("up", 0) + obj.get("down", 0)
                    total_bytes = obj.get("total", 0)
                    return {
                        "used_gb": round(used_bytes / 1024**3, 2),
                        "total_gb": round(total_bytes / 1024**3, 2) if total_bytes > 0 else -1,
                        "enable": obj.get("enable", True)
                    }
        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}")
        return None

    async def extend_client(self, xray_email: str, extra_days: int) -> bool:
        """Продлевает подписку клиента"""
        if not await self.login():
            return False
        try:
            sess = await self._get_session()
            # Получаем текущие данные клиента
            async with sess.get(
                f"{self.base_url}/panel/api/inbounds/getClientTrafficsById/{xray_email}",
                cookies=self.cookie,
                ssl=False
            ) as resp:
                data = await resp.json()
                if not data.get("success"):
                    return False
                obj = data.get("obj", {})
                current_expiry = obj.get("expiryTime", 0)
                now_ms = int(datetime.now().timestamp() * 1000)
                base = max(current_expiry, now_ms)
                new_expiry = base + extra_days * 86400000  # ms в сутках

            # Обновляем клиента
            update_payload = {**obj, "expiryTime": new_expiry}
            async with sess.post(
                f"{self.base_url}/panel/api/inbounds/updateClient/{obj.get('id', xray_email)}",
                json={"id": XRAY_INBOUND_ID, "settings": f'{{"clients": [{update_payload}]}}'},
                cookies=self.cookie,
                ssl=False
            ) as resp:
                result = await resp.json()
                return result.get("success", False)
        except Exception as e:
            logger.error(f"Ошибка продления: {e}")
            return False

    async def check_connection(self) -> bool:
        """Проверяет доступность 3x-ui панели"""
        return await self.login()

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()


# Глобальный экземпляр сервиса
xray_service = XrayPanelService()
