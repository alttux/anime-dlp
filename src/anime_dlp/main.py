import argparse
import sys
from pathlib import Path

from anime_dlp.config import DOWNLOAD_DIR
from anime_dlp.cli import run_cli


def main():
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Anime Downloader")
    parser.add_argument(
        "-d", "--dir", default=None, help="Директория для скачивания"
    )
    args = parser.parse_args()

    download_dir = Path(args.dir) if args.dir else DOWNLOAD_DIR
    download_dir.mkdir(parents=True, exist_ok=True)

    run_cli(download_dir)


if __name__ == "__main__":
    main()
