from pathlib import Path

import requests
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

from config import HEADERS


def download_episode(url: str, filepath: Path, quality: int):
    full_url = f"https:{url}{quality}.mp4"

    response = requests.get(full_url, headers=HEADERS, stream=True)
    response.raise_for_status()

    total = int(response.headers.get("content-length", 0))

    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
    ) as progress:
        task = progress.add_task(f"Downloading {filepath.name}", total=total)

        with open(filepath, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                progress.update(task, advance=len(chunk))
