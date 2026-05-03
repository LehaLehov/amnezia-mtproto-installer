"""Тесты кастомных исключений."""

from proxy_installer.exceptions import SSHCommandError


def test_ssh_command_error_message() -> None:
    err = SSHCommandError("ls -la", 2, "no such file")
    assert "ls -la" in str(err)
    assert err.exit_status == 2
    assert err.stderr == "no such file"
