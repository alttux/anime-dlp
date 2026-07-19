import argparse
from pathlib import Path

from config import DOWNLOAD_DIR
from cli import run_cli


def main():
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
