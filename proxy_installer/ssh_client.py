"""
Модуль для работы по SSH с использованием paramiko.
"""

import paramiko
from typing import Optional, Tuple
import socket
import logging
from rich.console import Console

from .models import ServerCredentials
from .exceptions import SSHConnectionError, SSHAuthenticationError, SSHCommandError

# Настроим логгер (хотя можно вынести его конфигурацию)
logger = logging.getLogger(__name__)


class ServerConnection:
    """Класс для управления SSH подключением к серверу."""

    def __init__(self, credentials: ServerCredentials, timeout: int = 10):
        """
        Инициализация подключения.

        Args:
            credentials (ServerCredentials): Валидированные креды.
            timeout (int): Таймаут на операции подключения в секундах.
        """
        self.credentials = credentials
        self.timeout = timeout
        self._client: Optional[paramiko.SSHClient] = None
        self._console = Console()

    @property
    def is_connected(self) -> bool:
        """Проверка активно ли подключение."""
        if self._client is None:
            return False
        transport = self._client.get_transport()
        return transport is not None and transport.is_active()

    def connect(self) -> None:
        """
        Подключается к серверу по SSH.
        Использует пароль, если он задан, либо RSA/Ed25519 ключ.
        """
        try:
            self._client = paramiko.SSHClient()
            self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            password = self.credentials.password if self.credentials.password else None
            
            self._client.connect(
                hostname=str(self.credentials.host),
                port=self.credentials.port,
                username=self.credentials.username,
                password=password,
                key_filename=self.credentials.key_path,
                timeout=self.timeout
            )
            logger.info(f"Successfully connected to {self.credentials.host}")

        except paramiko.AuthenticationException as e:
            logger.error("Authentication failed.")
            raise SSHAuthenticationError(f"Ошибка авторизации на {self.credentials.host}: неверный логин, пароль или ключ.") from e
        except (socket.error, paramiko.SSHException) as e:
            logger.error(f"Connection failed: {e}")
            raise SSHConnectionError(f"Не удалось подключиться к серверу {self.credentials.host}: {e}") from e

    def execute_command(self, command: str, check_status: bool = True) -> Tuple[int, str, str]:
        """
        Выполняет команду на удаленном сервере и ждет ее завершения.
        
        Args:
            command (str): Bash-команда для выполнения.
            check_status (bool): Если True, вызывает исключение при ненулевом коде возврата.
            
        Returns:
            Tuple[int, str, str]: Кортеж (код_возврата, stdout, stderr).
        """
        if not self.is_connected:
            raise SSHConnectionError("Нет активного подключения к серверу.")

        assert self._client is not None

        logger.debug(f"Executing: {command}")
        try:
            # paramiko's exec_command не является интерактивным, что идеально для скриптов
            stdin, stdout, stderr = self._client.exec_command(command, timeout=300)
            
            exit_status = stdout.channel.recv_exit_status()
            out = stdout.read().decode('utf-8').strip()
            err = stderr.read().decode('utf-8').strip()

            if check_status and exit_status != 0:
                logger.error(f"Command failed with code {exit_status}: {err}")
                raise SSHCommandError(command=command, exit_status=exit_status, stderr=err)

            return exit_status, out, err

        except paramiko.SSHException as e:
            raise SSHConnectionError(f"Ошибка выполнения команды по SSH: {e}") from e

    def check_os(self) -> str:
        """
        Проверяет операционную систему сервера.
        Возвращает идентификатор ОС (например, 'ubuntu', 'debian', 'centos').
        """
        try:
            # Читаем /etc/os-release
            _, stdout, _ = self.execute_command("cat /etc/os-release | grep '^ID='", check_status=False)
            if stdout:
                return stdout.split('=')[1].strip().strip('"').strip("'").lower()
            return "unknown"
        except Exception:
            return "unknown"

    def close(self) -> None:
        """Закрывает подключение."""
        if self._client:
            self._client.close()
            self._client = None
            logger.info(f"Connection to {self.credentials.host} closed.")

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
