import argparse
import sys
from pathlib import Path

from anime_dlp.config import DOWNLOAD_DIR
from anime_dlp.cli import run_cli
from anime_dlp.logger import ConsoleLogger


def main():
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Anime Downloader")
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
    args = parser.parse_args()

    download_dir = Path(args.dir) if args.dir else DOWNLOAD_DIR
    download_dir.mkdir(parents=True, exist_ok=True)

    def _run():
        if args.gui:
            from anime_dlp.gui import run_gui

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
