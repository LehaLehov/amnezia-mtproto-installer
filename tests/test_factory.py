"""Тесты фабрики установщиков."""


from proxy_installer.installers.factory import create_installer
from proxy_installer.models import ProxyType


def test_create_installer_mtproto() -> None:
    inst = create_installer(ProxyType.MTPROTO)
    assert hasattr(inst, "build_install_plan")
    assert callable(getattr(inst, "build_install_plan"))


def test_create_installer_amnezia() -> None:
    inst = create_installer(ProxyType.AMNEZIA_WG)
    assert hasattr(inst, "build_install_plan")
    assert callable(getattr(inst, "build_install_plan"))
