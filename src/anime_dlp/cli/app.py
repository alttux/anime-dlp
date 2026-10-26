import sys
import threading
from pathlib import Path

from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TaskID,
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
from anime_dlp.core.anime_service import get_anime_info, search_anime
from anime_dlp.core.episodes import DownloadEvents, EpisodeJob, download_episodes


class _RichEvents(DownloadEvents):
    """Одна строка rich-прогрессбара на серию."""

    def __init__(self, progress: Progress):
        self.progress = progress
        self.tasks: dict[str, TaskID] = {}

    def on_start(self, job: EpisodeJob, quality: int) -> None:
        label = f" ({quality}p)" if quality else ""
        show_info(f"Скачивание [bold]{job.filename}[/]{label} — {job.index} из {job.total}")
        self.tasks[job.filename] = self.progress.add_task(
            f"Downloading {job.filename}", total=None
        )

    def on_progress(self, job: EpisodeJob, downloaded: int, total: int) -> None:
        self.progress.update(
            self.tasks[job.filename], completed=downloaded, total=total or None
        )

    def on_done(self, job: EpisodeJob) -> None:
        show_success(f"{job.filename} сохранён")

    def on_error(self, job: EpisodeJob, message: str) -> None:
        show_error(f"{job.filename}: {message}")


def _download_all(selected: dict, translation_id: str, episodes: list[int], download_dir: Path):
    cancel_event = threading.Event()
    with Progress(
        TextColumn("[progress.description]{task.description}"),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        # Скачивание идёт в фоновом потоке, чтобы Ctrl+C (он всегда приходит в
        # главный поток) мог корректно остановить его: недокачанные куски
        # останутся в .part и продолжатся при следующем запуске.
        outcome: list = []
        worker = threading.Thread(
            target=lambda: outcome.append(
                download_episodes(
                    selected,
                    translation_id,
                    episodes,
                    download_dir,
                    _RichEvents(progress),
                    cancel_event,
                )
            ),
            daemon=True,
        )
        worker.start()
        try:
            while worker.is_alive():
                worker.join(0.2)
        except KeyboardInterrupt:
            cancel_event.set()
            show_info("Остановка... недокачанное продолжится при следующем запуске")
            worker.join()
    return outcome[0] if outcome else None


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
        elif isinstance(answer, tuple):
            start, end = answer
            eps_to_download = list(range(start, end + 1))
        else:
            eps_to_download = [answer]

    result = _download_all(selected, translation_id, eps_to_download, download_dir)
    if result is None or result.cancelled:
        show_error("Скачивание отменено")
        sys.exit(130)
    if result.failed:
        show_error(
            "Не удалось скачать: " + ", ".join(job.filename for job in result.failed)
        )
        sys.exit(1)

    console.print(
        f"\n[bold green]Готово![/] Файлы сохранены в [bold]{download_dir}[/]"
    )
