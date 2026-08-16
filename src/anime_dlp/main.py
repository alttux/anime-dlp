import argparse
import sys
from pathlib import Path

from anime_dlp import __version__
from anime_dlp.config import DOWNLOAD_DIR
from anime_dlp.cli import run_cli
from anime_dlp.cli.display import show_error
from anime_dlp.core import network
from anime_dlp.logger import ConsoleLogger


def main():
    # Консоль Windows по умолчанию использует однобайтовую кодовую страницу
    # (cp1252/cp1251 и т.п.), в которой нет кириллицы — без этого вывод
    # текста программы (справка, подсказки, ошибки) падает с
    # UnicodeEncodeError. На Linux/macOS stdout уже в UTF-8, reconfigure
    # здесь безвреден.
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Anime Downloader")
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"anime-dlp {__version__}",
    )
    parser.add_argument(
        "-d", "--dir", default=None, help="Директория для скачивания"
    )
    parser.add_argument(
        "--logging",
        action="store_true",
        help="Сохранять весь вывод консоли в anime-dlp.log",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Запустить графический интерфейс",
    )
    parser.add_argument(
        "-i",
        "--interface",
        default=None,
        help="Сетевой интерфейс для выхода в интернет (например, wlan0), в обход VPN/TUN",
    )
    args = parser.parse_args()

    download_dir = Path(args.dir) if args.dir else DOWNLOAD_DIR
    download_dir.mkdir(parents=True, exist_ok=True)

    if args.interface:
        if not network.SUPPORTED:
            show_error(
                "Привязка к сетевому интерфейсу (-i/--interface) поддерживается "
                f"только в Linux (текущая платформа: {sys.platform})."
            )
            sys.exit(1)
        available = network.list_interfaces()
        if args.interface not in available:
            show_error(
                f"Интерфейс '{args.interface}' не найден. "
                f"Доступные интерфейсы: {', '.join(available) or 'нет'}"
            )
            sys.exit(1)
        network.bind_to_interface(args.interface)

    def _run():
        if args.gui:
            try:
                from anime_dlp.gui import run_gui
            except ImportError as exc:
                show_error(
                    "Не удалось запустить графический интерфейс: не установлены "
                    f"GTK4/libadwaita/PyGObject ({exc}). Установите зависимости "
                    "GUI для вашей платформы — см. README.md."
                )
                sys.exit(1)

            run_gui(download_dir)
        else:
            run_cli(download_dir)

    if args.logging:
        log_path = download_dir / "anime-dlp.log"
        with ConsoleLogger(log_path):
            _run()
    else:
        _run()


if __name__ == "__main__":
    main()
