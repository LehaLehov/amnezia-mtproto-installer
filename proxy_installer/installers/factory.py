"""
Фабрика установщиков по типу прокси.

Чтобы добавить новый тип: нужно расширить create_installer() (и сам класс установщика).
Интерфейс (cli) трогать не нужно - он уже берёт установщик отсюда.
"""

from ..exceptions import InstallerUnavailableError
from ..models import ProxyType
from .base import BaseInstaller
from .mtproto import MTProtoInstaller


def create_installer(proxy_type: ProxyType) -> BaseInstaller:
    """
    Возвращает установщик для выбранного типа прокси.

    Args:
        proxy_type: Тип прокси, для которого нужно создать установщик.

    Returns:
        BaseInstaller: Экземпляр установщика (MTProtoInstaller или AmneziaInstaller).

    Raises:
        InstallerUnavailableError: Если тип прокси не поддерживается.
    """
    if proxy_type == ProxyType.MTPROTO:
        return MTProtoInstaller()
    if proxy_type == ProxyType.AMNEZIA_WG:
        from .amnezia import AmneziaInstaller
        return AmneziaInstaller()
    raise InstallerUnavailableError(
        f"Неизвестный тип прокси: {proxy_type!r}",
        proxy_type=proxy_type,
    )
