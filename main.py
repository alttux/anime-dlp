import argparse
import sys
from pathlib import Path

from config import DOWNLOAD_DIR
from cli import (
    ask_episode,
    ask_title,
    console,
    print_banner,
    show_anime_list,
    show_translations,
)
from core.anime_service import (
    get_anime_info,
    get_download_link,
    search_anime,
)
from core.downloader import download_episode


def main():
    parser = argparse.ArgumentParser(description="Anime Downloader")
    parser.add_argument(
        "-d", "--dir", default=None, help="Директория для скачивания"
    )
    args = parser.parse_args()

    download_dir = Path(args.dir) if args.dir else DOWNLOAD_DIR
    download_dir.mkdir(parents=True, exist_ok=True)

    print_banner()

    title = ask_title()
    console.print("\n[cyan]Поиск...[/]")

    items = search_anime(title)
    if not items:
        console.print("[red]Ничего не найдено[/]")
        sys.exit(1)

    idx = show_anime_list(items)
    selected = items[idx]

    sid = selected.get("shikimori_id")
    if not sid:
        console.print(
            "[red]У этого аниме нет shikimori_id, скачивание невозможно[/]"
        )
        sys.exit(1)

    console.print("\n[cyan]Получение информации об озвучках...[/]")

    info = get_anime_info(sid)
    translations = info["translations"]
    series_count = info["series_count"]

    tidx = show_translations(translations, series_count)
    translation = translations[tidx]
    translation_id = translation["id"]

    is_movie = series_count == 0 or series_count is None

    if is_movie:
        eps_to_download = [0]
    else:
        answer = ask_episode(series_count)
        if answer == "all":
            eps_to_download = list(range(1, series_count + 1))
        else:
            eps_to_download = [answer]

    for ep in eps_to_download:
        ep_label = "фильм" if ep == 0 else f"серия {ep}"
        console.print(f"\n[cyan]Получение ссылки на {ep_label}...[/]")

        link, quality, _ = get_download_link(sid, ep, translation_id)

        safe_title = "".join(
            c for c in selected["title"] if c.isalnum() or c in " .-_()"
        ).strip()
        if ep == 0:
            filename = f"{safe_title}.mp4"
        else:
            filename = f"{safe_title} - {ep:03d}.mp4"

        filepath = download_dir / filename

        console.print(f"[green]Скачивание {filename} ({quality}p)...[/]")
        download_episode(link, filepath, quality)

    console.print("\n[bold green]Готово![/]")


if __name__ == "__main__":
    main()
