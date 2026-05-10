"""Тесты фабрики установщиков."""

import pytest

from proxy_installer.installers.factory import create_installer, get_available_proxies, register
from proxy_installer.models import ProxyType
from proxy_installer.exceptions import InstallerUnavailableError
from proxy_installer.installers.base import BaseInstaller


def test_create_installer_mtproto() -> None:
    inst = create_installer(ProxyType.MTPROTO)
    assert hasattr(inst, "build_install_plan")
    assert callable(getattr(inst, "build_install_plan"))


def test_create_installer_amnezia() -> None:
    inst = create_installer(ProxyType.AMNEZIA_WG)
    assert hasattr(inst, "build_install_plan")
    assert callable(getattr(inst, "build_install_plan"))


def test_get_available_proxies() -> None:
    proxies = get_available_proxies()
    assert ProxyType.MTPROTO in proxies
    assert ProxyType.AMNEZIA_WG in proxies
    assert isinstance(proxies[ProxyType.MTPROTO], str)


def test_create_installer_unavailable() -> None:
    with pytest.raises(InstallerUnavailableError):
        # Передаем несуществующий тип прокси (игнорируем проверку типов mypy)
        create_installer("unknown_proxy_type")  # type: ignore


def test_register_new_installer() -> None:
    class DummyInstaller(BaseInstaller):
        def _run_installation_steps(self, connection):
            pass

    fake_type = "dummy_type"
    
    # Регистрируем новый фейковый установщик
    register(fake_type, "Dummy Proxy", DummyInstaller)  # type: ignore
    
    # Проверяем, что он появился в списке доступных
    proxies = get_available_proxies()
    assert fake_type in proxies  # type: ignore
    assert proxies[fake_type] == "Dummy Proxy"  # type: ignore
    
    # Проверяем, что фабрика умеет его создавать
    inst = create_installer(fake_type)  # type: ignore
    assert isinstance(inst, DummyInstaller)
    
    # Очищаем реестр после теста, чтобы не засорять глобальное состояние
    from proxy_installer.installers.factory import _REGISTRY
    if fake_type in _REGISTRY:
        del _REGISTRY[fake_type]
