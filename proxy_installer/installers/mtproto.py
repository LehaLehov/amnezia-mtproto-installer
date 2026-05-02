"""
Установщик MTProto прокси.
Наследуется от BaseInstaller, реализует шаги установки MTProto.
"""

import time
import secrets
import logging
from typing import Optional

from .base import BaseInstaller
from ..ssh_client import ServerConnection
from ..models import MTProtoConfig, InstallationResult, ProxyType
from ..exceptions import SSHCommandError

logger = logging.getLogger(__name__)


class MTProtoInstaller(BaseInstaller):
    """
    Класс для автоматизированной установки MTProto Proxy.
    Развертывает прокси, настраивает systemd сервис и запускает его.
    """

    def __init__(self, config: Optional[MTProtoConfig] = None):
        """
        Инициализация установщика.
        :param config: Настройки MTProto (порт, секрет). Если нет, сгенерирует по умолчанию.
        """
        self.config = config or MTProtoConfig(port=443)

        # Генерируем случайный секрет (32 байта в hex), если он не был передан
        if not self.config.secret:
            # Для MTProto Telegram секрет обычно 16 байт (32 символа hex), но часто делают 32 байта (64 символа)
            self.config.secret = secrets.token_hex(16)

    def _generate_tg_link(self, host: str) -> str:
        """
        Формирует красивую ссылку для подключения к Telegram.
        """
        return f"tg://proxy?server={host}&port={self.config.port}&secret={self.config.secret}"

    def _run_installation_steps(self, connection: ServerConnection) -> InstallationResult:
        """
        Конкретные шаги по установке MTProto Proxy на сервере.
        Использует Docker + Systemd для надежности, либо официальные бинарники.
        """
        logs = []
        try:
            logger.info("Обновление пакетов и установка зависимостей...")
            logs.append("Обновление пакетов...")
            connection.execute_command("apt-get update -y && apt-get install -y curl wget jq ca-certificates")

            logger.info("Установка Docker (если отсутствует)...")
            logs.append("Установка Docker...")
            connection.execute_command(
                "if ! command -v docker &> /dev/null; then curl -fsSL https://get.docker.com | bash; fi"
            )
            # Ждем пока docker daemon полностью запустится
            connection.execute_command("while ! docker info >/dev/null 2>&1; do sleep 1; done")

            # Настраиваем systemd сервис, который будет крутить MTProto-контейнер
            # Используем популярный легковесный образ telegrammessenger/mtproxy
            service_name = "mtproto-proxy.service"
            service_content = f"""
[Unit]
Description=MTProto Proxy Service
After=network.target docker.service
Requires=docker.service

[Service]
Restart=always
ExecStartPre=-/usr/bin/docker stop mtproto-proxy
ExecStartPre=-/usr/bin/docker rm mtproto-proxy
ExecStart=/usr/bin/docker run --name mtproto-proxy -p {self.config.port}:443 --rm -e SECRET={self.config.secret} telegrammessenger/mtproxy:latest
ExecStop=/usr/bin/docker stop -t 2 mtproto-proxy

[Install]
WantedBy=multi-user.target
"""
            logger.info("Создание systemd сервиса...")
            logs.append(f"Создание {service_name}...")
            
            # Записываем файл сервиса на удаленный сервер
            create_service_cmd = f"cat << 'EOF' > /etc/systemd/system/{service_name}\n{service_content.strip()}\nEOF"
            connection.execute_command(create_service_cmd)

            logger.info("Запуск сервиса в systemd...")
            logs.append("Перезагрузка systemd и запуск сервиса...")
            connection.execute_command("systemctl daemon-reload")
            connection.execute_command(f"systemctl enable {service_name}")
            connection.execute_command(f"systemctl restart {service_name}")

            # Ждем пару секунд для инициализации
            time.sleep(2)

            logger.info("Проверка статуса сервиса...")
            logs.append("Проверка статуса...")
            # Если сервис не запущен, is-active вернет non-zero код, и вызовется SSHCommandError
            try:
                connection.execute_command(f"systemctl is-active {service_name}")
            except SSHCommandError as e:
                # Если сервис упал, давайте вытащим логи из journalctl для лучшей диагностики
                _, logs_out, _ = connection.execute_command(f"journalctl -u {service_name} --no-pager -n 20", check_status=False)
                e.stderr += f"\n\nSystemd Logs:\n{logs_out}"
                raise e

            # Формируем результат
            tg_link = self._generate_tg_link(str(connection.credentials.host))
            
            return InstallationResult(
                proxy_type=ProxyType.MTPROTO,
                success=True,
                connection_links=[tg_link],
                logs="\n".join(logs) + "\nУстановка успешно завершена!"
            )

        except SSHCommandError as e:
            logger.error(f"Ошибка установки на шаге выполнения команды: {e}")
            logs.append(f"Ошибка команды: {e.command}\nStderr: {e.stderr}")
            return InstallationResult(
                proxy_type=ProxyType.MTPROTO,
                success=False,
                logs="\n".join(logs)
            )
