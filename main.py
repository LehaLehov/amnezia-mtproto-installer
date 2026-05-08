"""
Точка входа в программу.
"""
from proxy_installer.cli import CLI, parse_args


def main() -> None:
    """Запускает интерфейс приложения."""
    args = parse_args()
    app = CLI(dry_run=args.dry_run)
    app.run()


if __name__ == "__main__":
    main()
