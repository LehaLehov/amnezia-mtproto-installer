"""
Установщик Amnezia WG.
Наследуется от BaseInstaller, реализует шаги установки Amnezia WG (упрощенно через Docker).
"""

import time
import logging
import io
import qrcode  # type: ignore
from typing import List, Tuple

from .base import BaseInstaller
from ..ssh_client import ServerConnection
from ..models import InstallationResult, ProxyType
from ..exceptions import SSHCommandError

logger = logging.getLogger(__name__)


class AmneziaInstaller(BaseInstaller):
    """
    Класс для установки Amnezia WG.
    Развертывает контейнер и подготавливает директорию для ключей.
    """
    
    def __init__(self, port: int = 51820):
        self.port = port
        
    def _core_ssh_steps(self) -> List[Tuple[str, str]]:
        return [
            ("Обновление пакетов", "apt-get update -y && apt-get install -y curl wget jq ca-certificates wireguard-tools"),
            ("Установка Docker", "if ! command -v docker &> /dev/null; then curl -fsSL https://get.docker.com | bash; fi"),
            ("Создание конфиг-директории", "mkdir -p /opt/amnezia-wg"),
            ("Удаление старого контейнера (если есть)", "docker rm -f amnezia-wg || true"),
            ("Запуск контейнера Amnezia WG",
             f"docker run -d --name amnezia-wg --cap-add=NET_ADMIN --cap-add=SYS_MODULE "
             f"-p {self.port}:51820/udp -v /opt/amnezia-wg:/etc/amnezia/amneziawg --restart always "
             "amneziavpn/amnezia-wg:latest")
        ]
        
    def build_install_plan(self) -> List[Tuple[str, str]]:
        plan = list(self._core_ssh_steps())
        plan.append(("Проверка статуса", "docker ps | grep amnezia-wg"))
        return plan
        
    def dry_run_failure_log_command(self) -> str:
        return "docker logs amnezia-wg --tail 20"
        
    def _run_installation_steps(self, connection: ServerConnection) -> InstallationResult:
        logs: List[str] = []
        try:
            for title, cmd in self._core_ssh_steps():
                logger.info("%s", title)
                logs.append(title + "...")
                connection.execute_command(cmd)

            time.sleep(2)
            
            # Простая проверка что контейнер запущен
            connection.execute_command("docker ps | grep amnezia-wg")
            
            # Генерация заглушки конфига клиента
            client_conf = f"""[Interface]
PrivateKey = (Нужно сгенерировать клиентский ключ)
Address = 10.8.0.2/24
DNS = 1.1.1.1

[Peer]
PublicKey = (Ваш публичный ключ сервера из /opt/amnezia-wg)
Endpoint = {connection.credentials.host}:{self.port}
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = 25"""

            # Создаем QR код из текста конфига
            qr = qrcode.QRCode()
            qr.add_data(client_conf)
            qr.make(fit=True)
            buf = io.StringIO()
            qr.print_ascii(out=buf)
            qr_str = buf.getvalue()

            return InstallationResult(
                proxy_type=ProxyType.AMNEZIA_WG,
                success=True,
                connection_links=["Конфиги находятся в /opt/amnezia-wg на сервере."],
                logs="\n".join(logs) + f"\n\nУстановка завершена. Пример конфига клиента:\n{client_conf}\n\nQR-код для сканирования телефоном:\n{qr_str}",
            )
        except SSHCommandError as e:
            logger.error("Ошибка установки: %s", e)
            logs.append(f"Ошибка команды: {e.command}\nStderr: {e.stderr}")
            return InstallationResult(
                proxy_type=ProxyType.AMNEZIA_WG,
                success=False,
                logs="\n".join(logs),
            )
