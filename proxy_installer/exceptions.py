"""
Кастомные исключения для автоустановщика прокси.
"""

from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .models import ProxyType


class ProxyInstallerError(Exception):
    """Базовое исключение для всех ошибок приложения."""
    pass


class SSHConnectionError(ProxyInstallerError):
    """Ошибка при подключении к удаленному серверу по SSH."""
    pass


class SSHAuthenticationError(SSHConnectionError):
    """Ошибка авторизации по SSH (неверный пароль или ключ)."""
    pass


class SSHCommandError(ProxyInstallerError):
    """Ошибка при выполнении команды на удаленном сервере."""
    def __init__(self, command: str, exit_status: int, stderr: str):
        self.command = command
        self.exit_status = exit_status
        self.stderr = stderr
        super().__init__(f"Command '{command}' failed with status {exit_status}:\n{stderr}")


class UnsupportedOSError(ProxyInstallerError):
    """Ошибка: неподдерживаемая операционная система (например, не Ubuntu/Debian)."""
    pass


class InstallationError(ProxyInstallerError):
    """Общая ошибка в процессе установки прокси."""
    pass


class InstallerUnavailableError(ProxyInstallerError):
    """
    Нет установщика для выбранного типа прокси (не реализовано или ещё в разработке).
    """
    def __init__(self, message: str, proxy_type: Optional["ProxyType"] = None) -> None:
        self.proxy_type = proxy_type
        super().__init__(message)
