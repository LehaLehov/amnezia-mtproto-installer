"""
Модели данных для автоустановщика прокси.
Используется dataclasses (встроенный модуль Python) для хранения конфигурации.
"""

from dataclasses import dataclass, field
from typing import Optional, List
from enum import Enum


class ProxyType(str, Enum):
    """Тип устанавливаемого прокси."""
    MTPROTO = "mtproto"
    AMNEZIA_WG = "amnezia_wg"


@dataclass
class ServerCredentials:
    """Креды для подключения к серверу."""
    host: str
    port: int = 22
    username: str = "root"
    password: Optional[str] = None
    key_path: Optional[str] = None

    def __post_init__(self):
        if not self.host:
            raise ValueError("IP-адрес сервера не может быть пустым.")
        if not (1 <= self.port <= 65535):
            raise ValueError("Порт должен быть в диапазоне от 1 до 65535.")
        if not self.username:
            raise ValueError("Имя пользователя не может быть пустым.")
        if not self.password and not self.key_path:
            raise ValueError("Необходимо указать либо пароль, либо путь к SSH ключу.")


@dataclass
class MTProtoConfig:
    """Конфигурация для MTProto прокси."""
    port: int = 443
    secret: Optional[str] = None
    tag: Optional[str] = None

    def __post_init__(self):
        if not (1 <= self.port <= 65535):
            raise ValueError("Порт MTProto должен быть в диапазоне от 1 до 65535.")
        if self.secret is not None:
            if len(self.secret) < 32:
                raise ValueError("Секрет MTProto должен быть не менее 32 символов.")
            if not all(c in "0123456789abcdefABCDEF" for c in self.secret):
                raise ValueError("Секрет MTProto должен состоять только из шестнадцатеричных символов (0-9, a-f).")


@dataclass
class InstallationResult:
    """Результат установки прокси."""
    proxy_type: ProxyType
    success: bool
    connection_links: List[str] = field(default_factory=list)
    logs: str = ""
