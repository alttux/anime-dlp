from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from anime_dlp.core.anime_info import extract_anime_info, has_any_info
from anime_dlp.labels import TYPE_MAP

console = Console()


def print_banner():
    banner = Panel(
        "[bold cyan]Anime Downloader[/]\n[dim]Скачивай аниме с плеера Kodik[/]",
        border_style="cyan",
        box=box.ROUNDED,
        padding=(1, 2),
    )
    console.print(banner)


def show_anime_table(items: list[dict]):
    table = Table(
        title="Найдено аниме",
        box=box.MINIMAL_HEAVY_HEAD,
        border_style="cyan",
        header_style="bold cyan",
    )
    table.add_column("№", style="dim", width=4, no_wrap=True)
    table.add_column("Название")
    table.add_column("Год", justify="center", width=6)
    table.add_column("Тип", width=12)
    table.add_column("Shikimori ID", style="bright_black", width=14)

    for i, item in enumerate(items, 1):
        raw_type = item.get("type", "")
        anime_type = TYPE_MAP.get(raw_type, raw_type)
        table.add_row(
            str(i),
            f"[bold]{item.get('title', 'Unknown')}[/]",
            str(item.get("year", "")),
            anime_type,
            str(item.get("shikimori_id") or "—"),
        )

    console.print(table)


def show_anime_info(item: dict):
    info = extract_anime_info(item)
    if not has_any_info(info):
        return

    facts = []
    if info.status:
        facts.append(f"Статус: {info.status}")
    if info.episodes_total:
        if info.episodes_aired and info.episodes_aired != info.episodes_total:
            facts.append(f"Эпизоды: {info.episodes_aired}/{info.episodes_total}")
        else:
            facts.append(f"Эпизоды: {info.episodes_total}")
    elif info.episodes_aired:
        facts.append(f"Эпизоды: {info.episodes_aired}")
    if info.score:
        rating = f"Рейтинг: {info.score}"
        if info.votes:
            rating += f" ({info.votes} голосов)"
        facts.append(rating)
    if info.genres:
        facts.append(f"Жанры: {', '.join(info.genres)}")
    if info.studios:
        facts.append(f"Студия: {', '.join(info.studios)}")

    body = "  ·  ".join(facts)
    if info.description:
        body = f"{body}\n\n{info.description}" if body else info.description
    if info.poster_url:
        body = f"{body}\n\nПостер: {info.poster_url}" if body else f"Постер: {info.poster_url}"

    panel = Panel(
        body,
        title=f"[bold cyan]{item.get('title', '')}[/]",
        border_style="cyan",
        box=box.ROUNDED,
        padding=(1, 2),
    )
    console.print(panel)


def show_translations_table(translations: list[dict], series_count: int):
    table = Table(
        title=f"Доступные озвучки  ·  всего серий: [bold]{series_count}[/]",
        box=box.MINIMAL_HEAVY_HEAD,
        border_style="green",
        header_style="bold green",
    )
    table.add_column("№", style="dim", width=4, no_wrap=True)
    table.add_column("Тип", width=14)
    table.add_column("Название")

    for i, t in enumerate(translations, 1):
        type_style = "cyan" if t["type"] == "Озвучка" else "magenta"
        table.add_row(
            str(i),
            f"[{type_style}]{t['type']}[/]",
            t["name"],
        )

    console.print(table)


def show_error(message: str):
    console.print(f"\n[bold red]Ошибка:[/] {message}\n")


def show_success(message: str):
    console.print(f"[bold green]✓[/] {message}")


def show_info(message: str):
    console.print(f"[blue]ℹ[/] {message}")
