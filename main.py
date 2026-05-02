"""
Точка входа в программу.
"""
from proxy_installer.cli import CLI


def main():
    """Запускает интерфейс приложения."""
    app = CLI()
    app.run()


if __name__ == "__main__":
    main()
