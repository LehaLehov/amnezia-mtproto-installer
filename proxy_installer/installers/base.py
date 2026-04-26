"""
Базовый класс и протокол для всех установщиков прокси.
Используется typing.Protocol для статической типизации интерфейсов.
"""

from typing import Protocol, runtime_checkable
from abc import ABC, abstractmethod

from ..models import InstallationResult
from ..ssh_client import ServerConnection
from ..exceptions import InstallationError, UnsupportedOSError


@runtime_checkable
class InstallerProtocol(Protocol):
    """
    Протокол, описывающий минимальный интерфейс установщика прокси.
    Любой класс-инсталлятор должен реализовывать метод install().
    """
    def install(self, connection: ServerConnection) -> InstallationResult:
        """
        Основной метод установки.
        :param connection: Экземпляр соединения ServerConnection (через paramiko).
        :return: InstallationResult с результатом деплоя.
        """
        ...


class BaseInstaller(ABC):
    """
    Абстрактный базовый класс установщика.
    Интегрирует общие проверки и методы, чтобы избежать дублирования кода.
    """

    SUPPORTED_OS = ["ubuntu", "debian"]

    def _check_os(self, connection: ServerConnection) -> None:
        """
        Проверяет, поддерживается ли операционная система сервера.
        :raises UnsupportedOSError: Если ОС не поддерживается.
        """
        server_os = connection.check_os()
        if server_os not in self.SUPPORTED_OS:
            raise UnsupportedOSError(
                f"Неподдерживаемая ОС: {server_os}. "
                f"Ожидалось: {', '.join(self.SUPPORTED_OS)}."
            )

    @abstractmethod
    def _run_installation_steps(self, connection: ServerConnection) -> InstallationResult:
        """
        Шаги установки конкретного прокси (должно быть реализовано в подклассе).
        """
        pass

    def install(self, connection: ServerConnection) -> InstallationResult:
        """
        Шаблонный метод для установки прокси.
        Выполняет базовые проверки, а затем делегирует работу подклассу.
        """
        try:
            # Сначала проверяем ОС
            self._check_os(connection)
            
            # Затем запускаем специфичные шаги установки
            return self._run_installation_steps(connection)
            
        except UnsupportedOSError as e:
            raise e  # Пробрасываем выше для обработки в CLI
        except Exception as e:
            raise InstallationError(f"Ошибка во время установки: {e}") from e
