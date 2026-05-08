"""Тесты для данных."""

import pytest

from proxy_installer.models import (
    InstallationResult,
    MTProtoConfig,
    ProxyType,
    ServerCredentials,
)


def test_server_credentials_ok() -> None:
    creds = ServerCredentials(host="192.168.1.1", password="secret")
    assert creds.host == "192.168.1.1"
    assert creds.port == 22
    assert creds.username == "root"
    assert creds.password == "secret"


def test_server_credentials_empty_host_raises() -> None:
    with pytest.raises(ValueError, match="пустым"):
        ServerCredentials(host="")


def test_mtproto_config_defaults() -> None:
    cfg = MTProtoConfig()
    assert cfg.port == 443
    assert cfg.secret is None


def test_installation_result_defaults() -> None:
    r = InstallationResult(proxy_type=ProxyType.MTPROTO, success=True)
    assert r.connection_links == []
    assert r.logs == ""
