"""
Установщики различных протоколов.
"""
from .base import BaseInstaller, InstallerProtocol
from .mtproto import MTProtoInstaller

__all__ = ["BaseInstaller", "InstallerProtocol", "MTProtoInstaller"]
