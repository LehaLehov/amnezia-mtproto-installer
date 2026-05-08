"""
Установщики различных протоколов.
"""
from .base import BaseInstaller, InstallerProtocol
from .mtproto import MTProtoInstaller
from .factory import create_installer

__all__ = ["BaseInstaller", "InstallerProtocol", "MTProtoInstaller", "create_installer"]
