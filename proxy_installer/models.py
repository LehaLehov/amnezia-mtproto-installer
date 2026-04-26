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


@dataclass
class MTProtoConfig:
    """Конфигурация для MTProto прокси."""
    port: int = 443
    secret: Optional[str] = None
    tag: Optional[str] = None


@dataclass
class InstallationResult:
    """Результат установки прокси."""
    proxy_type: ProxyType
    success: bool
    connection_links: List[str] = field(default_factory=list)
    logs: str = ""
