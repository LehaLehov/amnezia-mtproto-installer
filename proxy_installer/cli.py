"""
Модуль содержит логику CLI (Command Line Interface).
"""

from typing import List, Optional, cast, Tuple

import argparse
import sys
import os
import pyperclip
import questionary
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn

from .models import ServerCredentials, ProxyType
from .ssh_client import ServerConnection
from .exceptions import ProxyInstallerError, InstallerUnavailableError
from .installers import create_installer
from .installers.factory import get_available_proxies


class CLI:
    """
    Класс инкапсулирует логику консольного взаимодействия с пользователем.
    Использует rich для оформления вывода и questionary для интерактивного меню.
    """

    def __init__(self, dry_run: bool = False):
        self.console = Console()
        self._dry_run_from_args = dry_run

    def print_welcome(self):
        """Выводит приветственный баннер."""
        welcome_text = Text("Добро пожаловать в Автоустановщик Прокси на VDS!\n", style="bold green")
        welcome_text.append("Скрипт настроит ваш сервер и выдаст готовые ссылки.", style="white")
        panel = Panel(welcome_text, title="Proxy Forge", border_style="cyan")
        self.console.print(panel)

    def ask_use_dry_run(self) -> bool:
        """Спрашиваем dry-run, если не передан флаг --dry-run."""
        if self._dry_run_from_args:
            return True
        choice = questionary.select(
            "Режим запуска:",
            choices=[
                "Обычная установка (подключение по SSH к серверу)",
                "Dry-run: только показать команды (без SSH и без изменений на VDS)",
                "Выход",
            ],
        ).ask()
        if choice == "Выход" or choice is None:
            sys.exit(0)
        return choice.startswith("Dry-run")

    def ask_credentials(self) -> ServerCredentials:
        """
        Запрашивает у пользователя данные сервера и возвращает валидную модель.
        Оборачивает процесс в цикл, если пользователь ошибся при вводе.
        Также предлагает выбрать сохраненные сервера.
        """
        from .server_manager import ServerManager
        
        saved = ServerManager.load_servers()
        if saved:
            choices = [f"{s['username']}@{s['host']}:{s['port']}" for s in saved] + ["Добавить новый сервер"]
            choice = questionary.select(
                "Выбор сервера:",
                choices=choices
            ).ask()
            
            if choice != "Добавить новый сервер" and choice is not None:
                idx = choices.index(choice)
                s = saved[idx]
                return ServerCredentials(
                    host=s["host"],
                    port=s.get("port", 22),
                    username=s.get("username", "root"),
                    password=s.get("password"),
                    key_path=s.get("key_path")
                )

        while True:
            host = questionary.text("🌐 IP адрес сервера (VDS):").ask()
            if not host:
                self.console.print("[red]Ввод отменен. Выход...[/red]")
                sys.exit(0)

            auth_method = questionary.select(
                "🔑 Выберите способ авторизации SSH:",
                choices=["Пароль", "SSH ключ (приватный)"],
            ).ask()

            password = None
            key_path = None

            if auth_method == "Пароль":
                password = questionary.password("🤫 Пароль пользователя root:").ask()
            else:
                key_path = questionary.path("📁 Путь к приватному ключу:").ask()
                if key_path:
                    key_path = key_path.strip('"').strip("'")
                    key_path = os.path.abspath(key_path)

            try:
                creds = ServerCredentials(
                    host=host,
                    password=password,
                    key_path=key_path,
                )
                
                # Спрашиваем, сохранить ли сервер
                save = questionary.confirm("Сохранить данные сервера для быстрого входа в будущем?").ask()
                if save:
                    ServerManager.save_server(creds)
                    self.console.print("[dim green]Сервер успешно сохранен в saved_servers.json[/dim green]")
                    
                return creds
            except ValueError as e:
                self.console.print("[bold red]Ошибка валидации введенных данных![/bold red]")
                self.console.print(f"[red] - {e}[/red]")
                self.console.print("[yellow]Попробуйте еще раз.\n[/yellow]")

    def select_proxy_type(self) -> ProxyType:
        """Предлагает пользователю выбрать тип прокси для установки."""
        proxies = get_available_proxies()
        # Инвертируем словарь для questionary: Имя -> ProxyType
        choices_map = {name: pt for pt, name in proxies.items()}
        choices_list = list(choices_map.keys()) + ["Выход"]
        
        choice = questionary.select(
            "🛠 Какой прокси вы хотите установить?",
            choices=choices_list,
        ).ask()

        if choice == "Выход" or choice is None:
            sys.exit(0)
            
        return choices_map[choice]

    def _print_dry_run(self, creds: ServerCredentials, proxy_type: ProxyType) -> None:
        """Показать план команд без SSH (фича от ассиста)."""
        self.console.print(
            Panel(
                "[bold yellow]Dry-run[/bold yellow]: подключения по SSH нет, на VDS ничего не выполняется и не меняется.\n"
                "Ниже - те же команды, что отправились бы на сервер при обычной установке.",
                title="Режим dry-run",
                border_style="yellow",
            )
        )

        try:
            installer = create_installer(proxy_type)
        except InstallerUnavailableError as e:
            self.console.print(f"[red]{e}[/red]")
            return

        plan_fn = getattr(installer, "build_install_plan", None)
        if not callable(plan_fn):
            self.console.print(
                f"[red]У установщика для «{proxy_type.value}» нет dry-run (метод build_install_plan). "
                f"Добавь его в класс установщика.[/red]"
            )
            return

        secret = getattr(getattr(installer, "config", None), "secret", None)
        if secret:
            self.console.print(
                f"\n[dim]Сгенерированный секрет (как при реальной установке): {secret}[/dim]\n"
            )

        plan = cast(List[Tuple[str, str]], plan_fn())
        for i, (title, cmd) in enumerate(plan, 1):
            self.console.print(f"\n[bold cyan]{i}. {title}[/bold cyan]")
            self.console.print(Panel(cmd, border_style="dim", title="bash"))

        self.console.print(
            "\n[dim]Если бы is-active упал, установщик дополнительно выполнил бы диагностику:[/dim]"
        )
        log_cmd_fn = getattr(installer, "dry_run_failure_log_command", None)
        if callable(log_cmd_fn):
            self.console.print(
                Panel(
                    log_cmd_fn(),
                    border_style="dim",
                    title="bash (только при ошибке)",
                )
            )

        link_fn = getattr(installer, "_generate_tg_link", None)
        if callable(link_fn):
            link = str(link_fn(creds.host))
            self.console.print("\n[bold blue]После успешной установки была бы такая ссылка для Telegram:[/bold blue]")
            self.console.print(Panel(link, border_style="green"))

    def run(self):
        """Основной цикл работы программы."""
        self.print_welcome()
        use_dry_run = self.ask_use_dry_run()
        creds = self.ask_credentials()
        proxy_type = self.select_proxy_type()

        if use_dry_run:
            self._print_dry_run(creds, proxy_type)
            return

        try:
            installer = create_installer(proxy_type)
        except InstallerUnavailableError as e:
            self.console.print(f"[bold red]{e}[/bold red]")
            sys.exit(1)

        self.console.print(f"\n[bold cyan]Начинаем установку {proxy_type.value}...[/bold cyan]")

        try:
            with ServerConnection(creds) as connection:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=self.console,
                ) as progress:
                    task = progress.add_task(
                        "[green]Установка прокси... (это может занять пару минут)[/green]", total=None
                    )

                    result = installer.install(connection)

                    progress.update(task, completed=100)

                if result.success:
                    self.console.print("\n[bold green]✅ Установка успешно завершена![/bold green]")
                    self.console.print(
                        "[bold yellow]⚠️ ВАЖНО: Подождите 1-2 минуты, пока прокси полностью инициализируется на сервере.[/bold yellow]"
                    )
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
                    self.console.print(
                        "[dim red](При переходе просто через браузер она может не открыться. "
                        "Используйте ВПН для браузера, либо вставляйте прямиком в десктопный/мобильный клиент Telegram).[/dim red]"
                    )

                    fw_instructions = installer.get_firewall_instructions()
                    if fw_instructions:
                        self.console.print("\n[bold magenta]🔌 Настройка портов (Firewall):[/bold magenta]")
                        self.console.print(
                            "Если прокси не подключается (бесконечное 'Соединение...'), убедитесь, что вы открыли порт в панели хостинга!"
                        )
                        self.console.print(fw_instructions)

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


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Автоустановщик прокси на VDS (MTProto и др.)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Показать команды установки без SSH и без изменений на сервере",
    )
    return parser.parse_args(argv)
