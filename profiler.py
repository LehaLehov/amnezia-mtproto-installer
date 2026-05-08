"""
Скрипт профилирования для анализа скорости работы модулей.
Выполняет сбор метрик времени для основных операций, таких как 
инициализация SSH-клиента, генерация планов установки и 
симуляция сетевых задержек (моки).
"""

import cProfile
import pstats
import io
import time
from unittest.mock import MagicMock

from proxy_installer.installers.mtproto import MTProtoInstaller
from proxy_installer.installers.amnezia import AmneziaInstaller
from proxy_installer.models import ServerCredentials
from proxy_installer.ssh_client import ServerConnection


def profile_mtproto_plan():
    """Профилирование генерации плана установки MTProto."""
    installer = MTProtoInstaller()
    for _ in range(100):
        installer.build_install_plan()

def profile_amnezia_plan():
    """Профилирование генерации плана установки Amnezia WG."""
    installer = AmneziaInstaller()
    for _ in range(100):
        installer.build_install_plan()

def profile_ssh_simulation():
    """Симуляция выполнения команд через SSH с моками."""
    creds = ServerCredentials(host="10.0.0.1", password="123")
    conn = ServerConnection(creds)
    conn._client = MagicMock()
    
    mock_stdout = MagicMock()
    mock_stderr = MagicMock()
    mock_stdout.channel.recv_exit_status.return_value = 0
    mock_stdout.read.return_value = b"ok\n"
    mock_stderr.read.return_value = b""
    conn._client.exec_command.return_value = (None, mock_stdout, mock_stderr)

    for _ in range(50):
        conn.execute_command("echo test")
        # Имитируем небольшую сетевую задержку
        time.sleep(0.01)

def main():
    print("Начинаем профилирование...")
    pr = cProfile.Profile()
    pr.enable()
    
    profile_mtproto_plan()
    profile_amnezia_plan()
    profile_ssh_simulation()
    
    pr.disable()
    print("Профилирование завершено.\n")
    
    s = io.StringIO()
    sortby = pstats.SortKey.CUMULATIVE
    ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
    ps.print_stats(20)
    
    with open("profiler_output.txt", "w", encoding="utf-8") as f:
        f.write(s.getvalue())
        
    print(s.getvalue())

if __name__ == "__main__":
    main()
