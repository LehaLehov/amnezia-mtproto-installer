"""
Фабрика установщиков по типу прокси.

Реестр установщиков позволяет добавлять новые типы прокси без изменения CLI.
При добавлении нового типа:
1. Добавьте его в ProxyType.
2. Зарегистрируйте в _REGISTRY ниже.
"""

from typing import Callable, Dict, Tuple

from ..exceptions import InstallerUnavailableError
from ..models import ProxyType
from .base import BaseInstaller
from .mtproto import MTProtoInstaller
from .amnezia import AmneziaInstaller

# Реестр доступных прокси: {ProxyType: ("Отображаемое имя", Класс установщика)}
_REGISTRY: Dict[ProxyType, Tuple[str, Callable[[], BaseInstaller]]] = {}


def register(proxy_type: ProxyType, name: str, factory_func: Callable[[], BaseInstaller]):
    """Регистрирует новый установщик в фабрике."""
    _REGISTRY[proxy_type] = (name, factory_func)


def get_available_proxies() -> Dict[ProxyType, str]:
    """Возвращает словарь доступных прокси {ProxyType: "Имя для меню"}."""
    return {pt: name for pt, (name, _) in _REGISTRY.items()}


def create_installer(proxy_type: ProxyType) -> BaseInstaller:
    """
    Возвращает экземпляр установщика для выбранного типа прокси.

    Raises:
        InstallerUnavailableError: Если тип прокси не зарегистрирован.
    """
    if proxy_type not in _REGISTRY:
        raise InstallerUnavailableError(
            f"Неизвестный тип прокси: {proxy_type!r}",
            proxy_type=proxy_type,
        )
    _, factory_func = _REGISTRY[proxy_type]
    return factory_func()


# --- Регистрация встроенных установщиков ---

register(ProxyType.MTPROTO, "MTProto Proxy (Telegram)", MTProtoInstaller)
register(ProxyType.AMNEZIA_WG, "Amnezia WG", AmneziaInstaller)
