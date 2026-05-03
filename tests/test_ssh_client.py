"""Тесты SSH-клиента с моками paramiko."""

from unittest.mock import MagicMock

import pytest

from proxy_installer.exceptions import SSHCommandError, SSHConnectionError
from proxy_installer.models import ServerCredentials
from proxy_installer.ssh_client import ServerConnection


def test_execute_command_without_connection_raises() -> None:
    creds = ServerCredentials(host="10.0.0.1")
    conn = ServerConnection(creds)
    with pytest.raises(SSHConnectionError, match="Нет активного"):
        conn.execute_command("echo hi")


def test_execute_command_success() -> None:
    creds = ServerCredentials(host="10.0.0.1")
    conn = ServerConnection(creds)
    mock_client = MagicMock()
    mock_stdout = MagicMock()
    mock_stderr = MagicMock()
    mock_stdout.channel.recv_exit_status.return_value = 0
    mock_stdout.read.return_value = b"ok\n"
    mock_stderr.read.return_value = b""
    mock_client.exec_command.return_value = (None, mock_stdout, mock_stderr)

    conn._client = mock_client
    code, out, err = conn.execute_command("echo ok", check_status=True)
    assert code == 0
    assert out == "ok"
    assert err == ""


def test_execute_command_failure_raises() -> None:
    creds = ServerCredentials(host="10.0.0.1")
    conn = ServerConnection(creds)
    mock_client = MagicMock()
    mock_stdout = MagicMock()
    mock_stderr = MagicMock()
    mock_stdout.channel.recv_exit_status.return_value = 1
    mock_stdout.read.return_value = b""
    mock_stderr.read.return_value = b"bad"
    mock_client.exec_command.return_value = (None, mock_stdout, mock_stderr)

    conn._client = mock_client
    with pytest.raises(SSHCommandError):
        conn.execute_command("false", check_status=True)
