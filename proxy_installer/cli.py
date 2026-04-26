"""
Модуль содержит логику CLI (Command Line Interface).
"""

import sys
import os
import pyperclip
import questionary
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt
from rich.progress import Progress, SpinnerColumn, TextColumn

from .models import ServerCredentials, ProxyType, MTProtoConfig
from .ssh_client import ServerConnection
from .exceptions import ProxyInstallerError
from .installers import MTProtoInstaller


class CLI:
    """
    Класс инкапсулирует логику консольного взаимодействия с пользователем.
    Использует rich для оформления вывода и questionary для интерактивного меню.
    """
    def __init__(self):
        self.console = Console()

    def print_welcome(self):
        """Выводит приветственный баннер."""
        welcome_text = Text("Добро пожаловать в Автоустановщик Прокси на VDS!\n", style="bold green")
        welcome_text.append("Скрипт настроит ваш сервер и выдаст готовые ссылки.", style="white")
        panel = Panel(welcome_text, title="Proxy Forge", border_style="cyan")
        self.console.print(panel)

    def ask_credentials(self) -> ServerCredentials:
        """
        Запрашивает у пользователя данные сервера и возвращает валидную модель.
        Оборачивает процесс в цикл, если пользователь ошибся при вводе.
        """
        while True:
            host = questionary.text("🌐 IP адрес сервера (VDS):").ask()
            if not host:
                self.console.print("[red]Ввод отменен. Выход...[/red]")
                sys.exit(0)

            auth_method = questionary.select(
                "🔑 Выберите способ авторизации SSH:",
                choices=["Пароль", "SSH ключ (приватный)"]
            ).ask()

            password = None
            key_path = None

            if auth_method == "Пароль":
                password = questionary.password("🤫 Пароль пользователя root:").ask()
            else:
                key_path = questionary.path("📁 Путь к приватному ключу:").ask()
                if key_path:
                    # Убираем лишние кавычки (часто бывают при drag-and-drop в Windows консоль)
                    key_path = key_path.strip('"').strip("'")
                    # Делаем путь абсолютным, чтобы скрипт точно нашел его в папке
                    key_path = os.path.abspath(key_path)

            try:
                creds = ServerCredentials(
                    host=host,
                    password=password,
                    key_path=key_path
                )
                return creds
            except ValueError as e:
                self.console.print(f"[bold red]Ошибка валидации введенных данных![/bold red]")
                self.console.print(f"[red] - {e}[/red]")
                self.console.print("[yellow]Попробуйте еще раз.\n[/yellow]")

    def select_proxy_type(self) -> ProxyType:
        """
        Предлагает пользователю выбрать тип прокси для установки.
        """
        choice = questionary.select(
            "🛠 Какой прокси вы хотите установить?",
            choices=[
                "MTProto Proxy (Telegram)",
                "Amnezia WG (Будет в Итерации 2)",
                "Выход"
            ]
        ).ask()

        if choice == "Выход":
            sys.exit(0)
        elif "Amnezia" in choice:
            self.console.print("[yellow]Поддержка Amnezia WG ожидается во второй итерации! Возвращаемся к MTProto...[/yellow]")
            return ProxyType.MTPROTO
        else:
            return ProxyType.MTPROTO

    def run(self):
        """
        Основной цикл работы программы.
        """
        self.print_welcome()
        creds = self.ask_credentials()
        proxy_type = self.select_proxy_type()

        # Создаем экземпляр установщика в зависимости от выбора
        # В будущем здесь будет фабрика (Factory pattern), когда добавятся другие протоколы
        installer = MTProtoInstaller()
        
        self.console.print(f"\n[bold cyan]Начинаем установку {proxy_type.value}...[/bold cyan]")

        try:
            with ServerConnection(creds) as connection:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=self.console
                ) as progress:
                    task = progress.add_task("[green]Установка прокси... (это может занять пару минут)[/green]", total=None)
                    
                    result = installer.install(connection)
                    
                    progress.update(task, completed=100)

                if result.success:
                    self.console.print("\n[bold green]✅ Установка успешно завершена![/bold green]")
                    self.console.print("[bold yellow]⚠️ ВАЖНО: Подождите 1-2 минуты, пока прокси полностью инициализируется на сервере.[/bold yellow]")
                    self.console.print("\n[bold blue]Ваши ссылки для подключения:[/bold blue]")
                    
                    for link in result.connection_links:
                        self.console.print(f"[bold yellow]{link}[/bold yellow]")
                        try:
                            pyperclip.copy(link)
                            self.console.print("[dim green](Ссылка автоматически скопирована в буфер обмена!)[/dim green]")
                        except Exception:
                            pass
                    
                    self.console.print("\n[bold cyan]💡 Как использовать ссылку:[/bold cyan]")
                    self.console.print("1. Вставьте её в 'Избранное' Telegram или отправьте кому-нибудь.")
                    self.console.print("2. Нажмите на неё [b]внутри приложения Telegram[/b].")
                    self.console.print("[dim red](При переходе просто через браузер она может не открыться. Используйте ВПН для браузера, либо вставляйте прямиком в десктопный/мобильный клиент Telegram).[/dim red]")

                    self.console.print("\n[bold magenta]🔌 Настройка портов (Firewall):[/bold magenta]")
                    self.console.print("Если прокси не подключается (бесконечное 'Соединение...'), убедитесь, что вы открыли порт в панели хостинга!")
                    self.console.print("[b]Для Selectel:[/b] Группы безопасности -> Входящий трафик -> Добавить правило (TCP, Порт 443, Источник 0.0.0.0/0).")

                    self.console.print("\n[dim]Логи установки:[/dim]")
                    self.console.print(Panel(result.logs, title="Logs", border_style="green"))
                else:
                    self.console.print("\n[bold red]❌ Ошибка при установке![/bold red]")
                    self.console.print(Panel(result.logs, title="Error Logs", border_style="red"))

        except ProxyInstallerError as e:
            self.console.print(f"\n[bold red]Критическая ошибка: {e}[/bold red]")
            sys.exit(1)
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Установка прервана пользователем.[/yellow]")
            sys.exit(0)
