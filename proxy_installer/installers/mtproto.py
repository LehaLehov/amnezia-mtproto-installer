"""
Установщик MTProto прокси.
Наследуется от BaseInstaller, реализует шаги установки MTProto.
"""

import time
import secrets
import logging
from typing import List, Optional, Tuple

from .base import BaseInstaller
from ..ssh_client import ServerConnection
from ..models import MTProtoConfig, InstallationResult, ProxyType
from ..exceptions import SSHCommandError

logger = logging.getLogger(__name__)

# Имя сервиса и официальный образ Telegram
SERVICE_NAME = "mtproto-proxy.service"
DOCKER_IMAGE = "telegrammessenger/proxy:latest"


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
        
        """
        Генерируем случайный секрет (16 байт -> 32 hex-символа), если не передали свой.
        Для MTProto обычно хватает 16 байт.
        """
        if not self.config.secret:
            self.config.secret = secrets.token_hex(16)

    def _systemd_unit_content(self) -> str:
        """Текст unit-файла: docker-контейнер с официальным образом telegrammessenger/proxy."""
        return f"""[Unit]
Description=MTProto Proxy Service
After=network.target docker.service
Requires=docker.service

[Service]
Restart=always
ExecStartPre=-/usr/bin/docker stop mtproto-proxy
ExecStartPre=-/usr/bin/docker rm mtproto-proxy
ExecStart=/usr/bin/docker run --name mtproto-proxy -p {self.config.port}:443 --rm -e SECRET={self.config.secret} {DOCKER_IMAGE}
ExecStop=/usr/bin/docker stop -t 2 mtproto-proxy

[Install]
WantedBy=multi-user.target"""

    def _write_unit_command(self) -> str:
        """Одна bash-команда: записать unit через heredoc."""
        body = self._systemd_unit_content()
        return f"cat << 'EOF' > /etc/systemd/system/{SERVICE_NAME}\n{body}\nEOF"

    def _core_ssh_steps(self) -> List[Tuple[str, str]]:
        """Команды до финальной проверки (без systemctl is-active)."""
        return [
            (
                "Обновить пакеты и поставить зависимости",
                "apt-get update -y && apt-get install -y curl wget jq ca-certificates",
            ),
            (
                "Установить Docker, если его ещё нет",
                "if ! command -v docker &> /dev/null; then curl -fsSL https://get.docker.com | bash; fi",
            ),
            (
                "Дождаться запуска docker daemon",
                "while ! docker info >/dev/null 2>&1; do sleep 1; done",
            ),
            (
                f"Создать /etc/systemd/system/{SERVICE_NAME}",
                self._write_unit_command(),
            ),
            ("Перечитать конфиг systemd", "systemctl daemon-reload"),
            (f"Включить автозапуск {SERVICE_NAME}", f"systemctl enable {SERVICE_NAME}"),
            (f"Перезапустить {SERVICE_NAME}", f"systemctl restart {SERVICE_NAME}"),
        ]

    def _check_active_command(self) -> Tuple[str, str]:
        return (
            "Проверить, что сервис активен",
            f"systemctl is-active {SERVICE_NAME}",
        )

    def build_install_plan(self) -> List[Tuple[str, str]]:
        """
        Полный план для dry-run: те же шаги, что и при реальной установке (в том же порядке).
        Пауза sleep(2) между restart и is-active — только в коде, отдельной строкой в плане.
        """
        plan = list(self._core_ssh_steps())
        plan.append(
            (
                "(локально в установщике: пауза 2 сек перед проверкой, на сервер не уходит)",
                "# sleep 2",
            )
        )
        plan.append(self._check_active_command())
        return plan

    def _generate_tg_link(self, host: str) -> str:
        """
        Формирует ссылку tg://proxy для быстрого подключения в Telegram.
        """
        return f"tg://proxy?server={host}&port={self.config.port}&secret={self.config.secret}"

    def dry_run_failure_log_command(self) -> str:
        """Команда journalctl, которую установщик выполняет при падении is-active (для вывода в dry-run)."""
        return f"journalctl -u {SERVICE_NAME} --no-pager -n 20"

    def _run_installation_steps(self, connection: ServerConnection) -> InstallationResult:
        """
        Шаги установки MTProto на сервере по SSH.
        Те же команды, что в _core_ssh_steps / build_install_plan: apt, docker, unit systemd, проверка.
        """
        logs: List[str] = []
        try:
            for title, cmd in self._core_ssh_steps():
                logger.info("%s", title)
                logs.append(title + "...")
                connection.execute_command(cmd)

            # Небольшая пауза перед проверкой, чтобы unit успел подняться
            time.sleep(2)

            logger.info("Проверка статуса сервиса...")
            logs.append("Проверка статуса...")
            try:
                _, check_cmd = self._check_active_command()
                connection.execute_command(check_cmd)
            except SSHCommandError as e:
                _, logs_out, _ = connection.execute_command(
                    f"journalctl -u {SERVICE_NAME} --no-pager -n 20", check_status=False
                )
                e.stderr += f"\n\nSystemd Logs:\n{logs_out}"
                raise e

            tg_link = self._generate_tg_link(str(connection.credentials.host))

            return InstallationResult(
                proxy_type=ProxyType.MTPROTO,
                success=True,
                connection_links=[tg_link],
                logs="\n".join(logs) + "\nУстановка успешно завершена!",
            )

        except SSHCommandError as e:
            logger.error("Ошибка установки: %s", e)
            logs.append(f"Ошибка команды: {e.command}\nStderr: {e.stderr}")
            return InstallationResult(
                proxy_type=ProxyType.MTPROTO,
                success=False,
                logs="\n".join(logs),
            )
