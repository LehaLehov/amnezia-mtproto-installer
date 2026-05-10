"""Тесты установщика MTProto."""

from unittest.mock import MagicMock
from proxy_installer.installers.mtproto import MTProtoInstaller, SERVICE_NAME
from proxy_installer.models import MTProtoConfig, ProxyType
from proxy_installer.exceptions import SSHCommandError


def test_build_install_plan_contains_apt_and_systemctl() -> None:
    inst = MTProtoInstaller()
    plan = inst.build_install_plan()
    joined = "\n".join(cmd for _, cmd in plan)
    assert "apt-get update" in joined
    assert "systemctl daemon-reload" in joined
    assert f"systemctl is-active {SERVICE_NAME}" in joined
    assert "telegrammessenger/proxy" in joined


def test_core_steps_match_plan_without_meta() -> None:
    inst = MTProtoInstaller()
    core = inst._core_ssh_steps()
    plan = inst.build_install_plan()
    assert len(plan) == len(core) + 2


def test_dry_run_failure_log_command() -> None:
    inst = MTProtoInstaller()
    cmd = inst.dry_run_failure_log_command()
    assert "journalctl" in cmd
    assert SERVICE_NAME in cmd


def test_get_firewall_instructions() -> None:
    inst = MTProtoInstaller(config=MTProtoConfig(port=54321))
    instructions = inst.get_firewall_instructions()
    assert "TCP" in instructions
    assert "54321" in instructions


def test_mtproto_generates_secret() -> None:
    inst = MTProtoInstaller()
    assert inst.config.secret is not None
    assert len(inst.config.secret) >= 32  # 16 bytes hex is 32 chars


def test_mtproto_custom_config() -> None:
    config = MTProtoConfig(port=8443, secret="0123456789abcdef0123456789abcdef")
    inst = MTProtoInstaller(config=config)
    assert inst.config.port == 8443
    assert inst.config.secret == "0123456789abcdef0123456789abcdef"


def test_systemd_unit_content() -> None:
    config = MTProtoConfig(port=8443, secret="0123456789abcdef0123456789abcdef")
    inst = MTProtoInstaller(config=config)
    content = inst._systemd_unit_content()
    assert "8443:443" in content
    assert "SECRET=0123456789abcdef0123456789abcdef" in content


def test_generate_tg_link() -> None:
    config = MTProtoConfig(port=8443, secret="0123456789abcdef0123456789abcdef")
    inst = MTProtoInstaller(config=config)
    link = inst._generate_tg_link("1.2.3.4")
    assert link == "tg://proxy?server=1.2.3.4&port=8443&secret=0123456789abcdef0123456789abcdef"


def test_run_installation_steps_success() -> None:
    inst = MTProtoInstaller()
    mock_conn = MagicMock()
    mock_conn.credentials.host = "1.2.3.4"
    # Для проверки `systemctl is-active` возвращаем успешный кортеж (exit_status, stdout, stderr)
    mock_conn.execute_command.return_value = (0, "active\n", "")
    
    result = inst._run_installation_steps(mock_conn)
    
    assert result.success is True
    assert result.proxy_type == ProxyType.MTPROTO
    assert len(result.connection_links) == 1
    assert "tg://proxy" in result.connection_links[0]
    assert mock_conn.execute_command.call_count > 0


def test_run_installation_steps_failure() -> None:
    inst = MTProtoInstaller()
    mock_conn = MagicMock()
    
    # Симулируем ошибку при выполнении команды (например, при скачивании образа или проверке статуса)
    mock_conn.execute_command.side_effect = SSHCommandError(
        command="some command", 
        exit_status=1, 
        stderr="mocked stderr error"
    )
    
    result = inst._run_installation_steps(mock_conn)
    
    assert result.success is False
    assert result.proxy_type == ProxyType.MTPROTO
    assert "mocked stderr error" in result.logs
