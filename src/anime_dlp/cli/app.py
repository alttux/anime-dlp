import sys
from pathlib import Path

from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from rich.status import Status

from anime_dlp.cli.display import (
    console,
    print_banner,
    show_anime_info,
    show_anime_table,
    show_error,
    show_info,
    show_success,
    show_translations_table,
)
from anime_dlp.cli.prompts import (
    ask_anime_choice,
    ask_episode,
    ask_title,
    ask_translation_choice,
)
from anime_dlp.core.anime_service import get_anime_info, get_download_link, search_anime
from anime_dlp.core.downloader import download_episode
from anime_dlp.filenames import sanitize_filename


def _download_with_progress(link: str, filepath: Path, quality: int):
    with Progress(
        TextColumn("[progress.description]{task.description}"),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
    ) as progress:
        task = progress.add_task(f"Downloading {filepath.name}", total=None)

        def on_progress(downloaded: int, total: int):
            if progress.tasks[0].total != total:
                progress.update(task, total=total)
            progress.update(task, completed=downloaded)

        download_episode(link, filepath, quality, on_progress=on_progress)


def run_cli(download_dir: Path):
    print_banner()

    title = ask_title()

    with Status("[bold cyan]Поиск...", spinner="dots"):
        items = search_anime(title)

    if not items:
        show_error("Ничего не найдено")
        sys.exit(1)

    show_anime_table(items)
    idx = ask_anime_choice(len(items))
    selected = items[idx]

    sid = selected.get("shikimori_id")
    if not sid:
        show_error("У этого аниме нет shikimori_id, скачивание невозможно")
        sys.exit(1)

    show_anime_info(selected)

    with Status("[bold cyan]Получение информации об озвучках...", spinner="dots"):
        info = get_anime_info(sid)

    translations = info["translations"]
    series_count = info["series_count"]

    show_translations_table(translations, series_count)
    tidx = ask_translation_choice(len(translations))
    translation = translations[tidx]
    translation_id = translation["id"]

    is_movie = series_count == 0 or series_count is None

    if is_movie:
        show_info("Определено как [bold]фильм[/]")
        eps_to_download = [0]
    else:
        answer = ask_episode(series_count)
        if answer == "all":
            eps_to_download = list(range(1, series_count + 1))
        else:
            eps_to_download = [answer]

    for ep in eps_to_download:
        ep_label = "фильм" if ep == 0 else f"серия {ep}"

        with Status(f"[cyan]Получение ссылки на {ep_label}...", spinner="dots"):
            link, quality, _ = get_download_link(sid, ep, translation_id)

        safe_title = sanitize_filename(selected["title"])
        if ep == 0:
            filename = f"{safe_title}.mp4"
        else:
            filename = f"{ep}.mp4"

        filepath = download_dir / filename
        show_info(f"Скачивание [bold]{filename}[/] ({quality}p)")
        _download_with_progress(link, filepath, quality)
        show_success(f"{filename} сохранён")

    console.print(
        f"\n[bold green]Готово![/] Файлы сохранены в [bold]{download_dir}[/]"
    )
