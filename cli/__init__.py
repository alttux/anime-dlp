from rich.console import Console
from rich.panel import Panel
from rich.prompt import IntPrompt, Prompt

console = Console()


def print_banner():
    console.print(Panel.fit("[bold cyan]Anime Downloader[/]", border_style="cyan"))


def ask_title() -> str:
    return Prompt.ask("[yellow]Введите название аниме[/]")


def show_anime_list(items: list[dict]) -> int:
    console.print("\n[bold]Найдено аниме:[/]")
    for i, item in enumerate(items, 1):
        title = item.get("title", "Unknown")
        year = item.get("year", "")
        sid = item.get("shikimori_id") or "-"
        console.print(f"  {i}. {title} ({year}) [shikimori: {sid}]")

    choice = IntPrompt.ask("\n[green]Выберите номер аниме[/]", default=1)
    return choice - 1


def show_translations(translations: list[dict], series_count: int) -> int:
    console.print(
        f"\n[bold]Доступные озвучки (всего серий: {series_count}):[/]"
    )
    for i, t in enumerate(translations, 1):
        console.print(f"  {i}. [{t['type']}] {t['name']}")

    choice = IntPrompt.ask("\n[green]Выберите номер озвучки[/]", default=1)
    return choice - 1


def ask_episode(series_count: int) -> int | str:
    console.print(f"\n[bold]Доступны серии с 1 по {series_count}[/]")
    answer = Prompt.ask(
        "[green]Введите номер серии (или 'all' для скачивания всех)[/]"
    )
    if answer.lower() == "all":
        return "all"
    return int(answer)
