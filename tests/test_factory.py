"""Тесты фабрики установщиков."""

import pytest

from proxy_installer.exceptions import InstallerUnavailableError
from proxy_installer.installers.factory import create_installer
from proxy_installer.models import ProxyType


def test_create_installer_mtproto() -> None:
    inst = create_installer(ProxyType.MTPROTO)
    assert hasattr(inst, "build_install_plan")
    assert callable(getattr(inst, "build_install_plan"))


def test_create_installer_amnezia_not_ready() -> None:
    with pytest.raises(InstallerUnavailableError, match="Amnezia") as exc_info:
        create_installer(ProxyType.AMNEZIA_WG)
    assert exc_info.value.proxy_type == ProxyType.AMNEZIA_WG
