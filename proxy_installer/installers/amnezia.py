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
            ("Генерация серверного конфига (если нет)",
             "if [ ! -f /opt/amnezia-wg/amneziawg0.conf ]; then "
             "SERVER_PRIVKEY=$(wg genkey); "
             "cat <<EOF > /opt/amnezia-wg/amneziawg0.conf\n"
             "[Interface]\n"
             "Address = 10.8.0.1/24\n"
             f"ListenPort = {self.port}\n"
             "PrivateKey = $SERVER_PRIVKEY\n"
             "Jc = 120\n"
             "Jmin = 23\n"
             "Jmax = 911\n"
             "S1 = 49\n"
             "S2 = 49\n"
             "H1 = 1\n"
             "H2 = 2\n"
             "H3 = 3\n"
             "H4 = 4\n"
             "PostUp = iptables -A FORWARD -i %i -j ACCEPT; iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE\n"
             "PostDown = iptables -D FORWARD -i %i -j ACCEPT; iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE\n"
             "EOF\n"
             "fi"),
            ("Удаление старого контейнера (если есть)", "docker rm -f amnezia-wg || true"),
            ("Запуск контейнера Amnezia WG",
             f"docker run -d --name amnezia-wg --cap-add=NET_ADMIN --cap-add=SYS_MODULE "
             f"--sysctl=\"net.ipv4.ip_forward=1\" --sysctl=\"net.ipv4.conf.all.src_valid_mark=1\" "
             f"-p {self.port}:51820/udp -v /opt/amnezia-wg:/etc/amnezia/amneziawg --restart always "
             "amneziavpn/amnezia-wg:latest")
        ]
        
    def build_install_plan(self) -> List[Tuple[str, str]]:
        plan = list(self._core_ssh_steps())
        plan.append(("Проверка статуса", "docker ps | grep amnezia-wg"))
        return plan
        
    def dry_run_failure_log_command(self) -> str:
        return "docker logs amnezia-wg --tail 20"

    def get_firewall_instructions(self) -> str:
        return (
            f"[b]Для Selectel:[/b] Группы безопасности -> Входящий трафик -> Добавить правило "
            f"(UDP, Порт {self.port}, Источник 0.0.0.0/0)."
        )
        
    def _run_installation_steps(self, connection: ServerConnection) -> InstallationResult:
        logs: List[str] = []
        try:
            for title, cmd in self._core_ssh_steps():
                logger.info("%s", title)
                logs.append(title + "...")
                connection.execute_command(cmd)

            time.sleep(2)
            
            # проверка что контейнер запущен
            connection.execute_command("docker ps | grep amnezia-wg")
            
            time.sleep(3)
            
            # Генерация ключей клиента
            _, client_privkey, _ = connection.execute_command("wg genkey", check_status=False)
            client_privkey = client_privkey.strip()
            
            _, client_pubkey, _ = connection.execute_command(f"echo '{client_privkey}' | wg pubkey", check_status=False)
            client_pubkey = client_pubkey.strip()
            
            # Получение публичного ключа сервера(изначально пусть ошибка)
            server_pubkey = "(Не удалось получить публичный ключ сервера)"
            
            # попытка прочитать конфиг
            _, wg0_content, _ = connection.execute_command("cat /opt/amnezia-wg/*.conf 2>/dev/null", check_status=False)
            
            server_privkey = None
            for line in wg0_content.splitlines():
                line = line.strip()
                if line.startswith("PrivateKey"):
                    parts = line.split("=")
                    if len(parts) >= 2:
                        server_privkey = parts[1].strip()
                        break
            
            is_valid = False
            if server_privkey:
                _, srv_pub, err = connection.execute_command(f"echo '{server_privkey}' | wg pubkey", check_status=False)
                if srv_pub.strip() and "Key is not" not in err:
                    server_pubkey = srv_pub.strip()
                    is_valid = True
            
            if not is_valid:
                # Если ключа нет, он пустой, или он невалидный (например $SERVER_PRIVKEY текстом)
                _, new_priv, _ = connection.execute_command("wg genkey", check_status=False)
                server_privkey = new_priv.strip()
                
                _, srv_pub, _ = connection.execute_command(f"echo '{server_privkey}' | wg pubkey", check_status=False)
                server_pubkey = srv_pub.strip()
                
                # Принудительная прописка ключа в конфиг сервера
                fix_cmd = (
                    "CONF_FILE=$(ls /opt/amnezia-wg/*.conf 2>/dev/null | head -n 1); "
                    "if [ -z \"$CONF_FILE\" ]; then CONF_FILE=/opt/amnezia-wg/amneziawg0.conf; fi; "
                    "if [ -f \"$CONF_FILE\" ]; then "
                    f"if grep -q '^PrivateKey' \"$CONF_FILE\"; then "
                    f"sed -i 's|^PrivateKey.*|PrivateKey = {server_privkey}|' \"$CONF_FILE\"; "
                    f"else printf 'PrivateKey = %s\\n' \"{server_privkey}\" >> \"$CONF_FILE\"; fi; "
                    "else "
                    f"printf '[Interface]\\nPrivateKey = %s\\nAddress = 10.8.0.1/24\\nListenPort = 51820\\n' \"{server_privkey}\" > \"$CONF_FILE\"; "
                    "fi; "
                    "docker restart amnezia-wg;"
                )
                connection.execute_command(fix_cmd, check_status=False)
                time.sleep(2)
                
            _, obfuscation_params, _ = connection.execute_command(
                "awk -F'=' '/^[[:space:]]*(Jc|Jmin|Jmax|S1|S2|H1|H2|H3|H4)/ {print $0}' /opt/amnezia-wg/*.conf 2>/dev/null",
                check_status=False
            )
            obfuscation_str = ("\n" + obfuscation_params.strip()) if obfuscation_params.strip() else ""

            # Расчет локального айпи для нового клиента (чтобы не было конфликтов при повторном запуске)
            _, peer_count_str, _ = connection.execute_command(
                "grep -c '\\[Peer\\]' /opt/amnezia-wg/*.conf 2>/dev/null | awk -F':' '{sum+=$2} END {print sum}'",
                check_status=False
            )
            try:
                peer_count = int(peer_count_str.strip() or 0)
            except ValueError:
                peer_count = 0
            
            client_ip_last_octet = peer_count + 2
            if client_ip_last_octet > 254:
                client_ip_last_octet = 254  # Ограничение простой сети /24 единицы в маске
            client_ip = f"10.8.0.{client_ip_last_octet}"

            # Добавление пира на сервер, если конфиг существует
            add_peer_cmd = (
                "CONF_FILE=$(ls /opt/amnezia-wg/*.conf 2>/dev/null | head -n 1); "
                "if [ -n \"$CONF_FILE\" ]; then "
                f"if ! grep -q '{client_pubkey}' \"$CONF_FILE\"; then "
                f"printf '\\n[Peer]\\nPublicKey = %s\\nAllowedIPs = %s/32\\n' \"{client_pubkey}\" \"{client_ip}\" >> \"$CONF_FILE\"; "
                "docker restart amnezia-wg; "
                "fi; "
                "fi"
            )
            connection.execute_command(add_peer_cmd, check_status=False)
            
            # Генерация конфига клиента
            client_conf = f"""[Interface]
PrivateKey = {client_privkey if client_privkey else '(Ошибка генерации)'}
Address = {client_ip}/24
DNS = 1.1.1.1{obfuscation_str}

[Peer]
PublicKey = {server_pubkey}
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
