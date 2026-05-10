"""Тесты плана установки Amnezia WG (dry-run)."""

from unittest.mock import MagicMock
from proxy_installer.installers.amnezia import AmneziaInstaller
from proxy_installer.models import ProxyType
from proxy_installer.exceptions import SSHCommandError


def test_build_install_plan_contains_docker() -> None:
    inst = AmneziaInstaller(port=51820)
    plan = inst.build_install_plan()
    joined = "\n".join(cmd for _, cmd in plan)
    assert "apt-get update" in joined
    assert "docker run -d --name amnezia-wg" in joined
    assert "51820:51820/udp" in joined


def test_core_steps_match_plan_without_meta() -> None:
    inst = AmneziaInstaller()
    core = inst._core_ssh_steps()
    plan = inst.build_install_plan()
    assert len(plan) == len(core) + 1


def test_dry_run_failure_log_command() -> None:
    inst = AmneziaInstaller()
    cmd = inst.dry_run_failure_log_command()
    assert "docker logs amnezia-wg" in cmd


def test_get_firewall_instructions() -> None:
    inst = AmneziaInstaller(port=12345)
    instructions = inst.get_firewall_instructions()
    assert "UDP" in instructions
    assert "12345" in instructions


def test_run_installation_steps_success() -> None:
    inst = AmneziaInstaller()
    mock_conn = MagicMock()
    mock_conn.credentials.host = "1.2.3.4"
    # Мокаем успешное выполнение всех команд (в т.ч. grep amnezia-wg)
    mock_conn.execute_command.return_value = (0, "docker container amnezia-wg up", "")
    
    result = inst._run_installation_steps(mock_conn)
    
    assert result.success is True
    assert result.proxy_type == ProxyType.AMNEZIA_WG
    assert len(result.connection_links) == 1
    assert "Конфиги находятся в" in result.connection_links[0]
    assert "QR-код" in result.logs
    assert mock_conn.execute_command.call_count > 0


def test_run_installation_steps_failure() -> None:
    inst = AmneziaInstaller()
    mock_conn = MagicMock()
    
    # Симулируем ошибку при выполнении команды (например, docker не установился)
    mock_conn.execute_command.side_effect = SSHCommandError(
        command="docker run ...",
        exit_status=1,
        stderr="mocked stderr error"
    )

    result = inst._run_installation_steps(mock_conn)
    
    assert result.success is False
    assert result.proxy_type == ProxyType.AMNEZIA_WG
    assert "mocked stderr error" in result.logs
