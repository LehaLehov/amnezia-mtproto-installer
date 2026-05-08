"""
Менеджер серверов для локального сохранения кредов.
"""

import json
import os
from typing import List, Dict, Any

from .models import ServerCredentials

CONFIG_PATH = "saved_servers.json"


class ServerManager:
    """Класс для сохранения и загрузки серверов в локальный JSON файл."""
    
    @staticmethod
    def load_servers() -> List[Dict[str, Any]]:
        """Загружает список сохраненных серверов."""
        if not os.path.exists(CONFIG_PATH):
            return []
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    @staticmethod
    def save_server(creds: ServerCredentials) -> None:
        """Сохраняет сервер в локальный файл, если его там еще нет."""
        servers = ServerManager.load_servers()
        
        # Обновляем, если такой хост уже есть
        for s in servers:
            if s["host"] == creds.host:
                s.update({
                    "port": creds.port,
                    "username": creds.username,
                    "password": creds.password,
                    "key_path": creds.key_path,
                })
                break
        else:
            servers.append({
                "host": creds.host,
                "port": creds.port,
                "username": creds.username,
                "password": creds.password,
                "key_path": creds.key_path,
            })
            
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(servers, f, indent=4)
